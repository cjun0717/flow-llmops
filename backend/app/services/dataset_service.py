#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库服务（async，迁移自 imooc dataset_service.py 的 CRUD 部分 + hit 检索）。"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.dataset_entity import DEFAULT_DATASET_DESCRIPTION_FORMATTER
from app.exceptions import FailException, NotFoundException, ValidateException
from app.models.app import AppDatasetJoin
from app.models.dataset import Dataset, DatasetQuery, Document, Segment
from app.models.account import Account
from app.models.upload_file import UploadFile
from app.schemas.dataset import (
    CreateDatasetReq,
    DatasetDetailData,
    DatasetListItemData,
    DatasetQueryData,
    GetDatasetsWithPageReq,
    HitDocumentData,
    HitReq,
    HitRespItem,
    UpdateDatasetReq,
)
from app.schemas.response import PageData, page_data


class DatasetService:
    """知识库 CRUD 服务"""

    @staticmethod
    async def _get_dataset_owned(dataset_id: UUID, account: Account, db: AsyncSession) -> Dataset:
        """获取知识库并校验权限"""
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("该知识库不存在")
        return dataset

    @staticmethod
    async def create_dataset(req: CreateDatasetReq, account: Account, db: AsyncSession) -> Dataset:
        """创建知识库"""
        # 1.检测同名
        result = await db.execute(
            select(Dataset).where(Dataset.account_id == account.id, Dataset.name == req.name)
        )
        if result.scalar_one_or_none() is not None:
            raise ValidateException(f"该知识库{req.name}已存在")

        # 2.补充默认描述
        description = req.description
        if not description or not description.strip():
            description = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(name=req.name)

        # 3.创建记录
        dataset = Dataset(
            account_id=account.id,
            name=req.name,
            icon=req.icon,
            description=description,
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)
        return dataset

    @staticmethod
    async def get_dataset_detail(dataset_id: UUID, account: Account, db: AsyncSession) -> DatasetDetailData:
        """获取知识库详情（含统计字段）"""
        dataset = await DatasetService._get_dataset_owned(dataset_id, account, db)
        return await DatasetService._to_detail(dataset, db)

    @staticmethod
    async def update_dataset(
        dataset_id: UUID, req: UpdateDatasetReq, account: Account, db: AsyncSession
    ) -> None:
        """更新知识库"""
        dataset = await DatasetService._get_dataset_owned(dataset_id, account, db)

        # 重名检测
        result = await db.execute(
            select(Dataset).where(
                Dataset.account_id == account.id,
                Dataset.name == req.name,
                Dataset.id != dataset_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ValidateException(f"该知识库名称{req.name}已存在，请修改")

        description = req.description
        if not description or not description.strip():
            description = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(name=req.name)

        dataset.name = req.name
        dataset.icon = req.icon
        dataset.description = description
        await db.commit()

    @staticmethod
    async def delete_dataset(dataset_id: UUID, account: Account, db: AsyncSession) -> None:
        """删除知识库（删 PG 记录 + 触发 Celery 删除向量）"""
        dataset = await DatasetService._get_dataset_owned(dataset_id, account, db)
        try:
            await db.delete(dataset)
            # 删除应用关联
            await db.execute(
                select(AppDatasetJoin).where(AppDatasetJoin.dataset_id == dataset_id)
            )
            from sqlalchemy import delete as sa_delete
            await db.execute(sa_delete(AppDatasetJoin).where(AppDatasetJoin.dataset_id == dataset_id))
            await db.commit()

            # 触发 Celery 任务删除向量（5b 实现向量部分，5a 占位）
            from app.tasks.dataset_task import delete_dataset as delete_dataset_task
            delete_dataset_task.delay(str(dataset_id))
        except Exception as e:
            logging.exception("删除知识库失败, dataset_id: %s, 错误: %s", dataset_id, e)
            raise FailException("删除知识库失败，请稍后重试")

    @staticmethod
    async def get_datasets_with_page(
        req: GetDatasetsWithPageReq, account: Account, db: AsyncSession
    ) -> PageData[DatasetListItemData]:
        """知识库分页列表"""
        filters = [Dataset.account_id == account.id]
        if req.search_word:
            filters.append(Dataset.name.ilike(f"%{req.search_word}%"))

        # 总数
        count_result = await db.execute(
            select(func.count()).select_from(Dataset).where(*filters)
        )
        total_record = count_result.scalar() or 0

        # 分页数据
        result = await db.execute(
            select(Dataset)
            .where(*filters)
            .order_by(desc(Dataset.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        datasets = result.scalars().all()

        items = [await DatasetService._to_list_item(d, db) for d in datasets]
        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @staticmethod
    async def get_dataset_queries(
        dataset_id: UUID, account: Account, db: AsyncSession
    ) -> list[DatasetQueryData]:
        """获取知识库最近 10 条查询记录"""
        await DatasetService._get_dataset_owned(dataset_id, account, db)
        result = await db.execute(
            select(DatasetQuery)
            .where(DatasetQuery.dataset_id == dataset_id)
            .order_by(desc(DatasetQuery.created_at))
            .limit(10)
        )
        return [DatasetQueryData.from_model(q) for q in result.scalars().all()]

    # ===== 统计字段（替代 imooc @property）=====

    @staticmethod
    async def _document_count(dataset_id: UUID, db: AsyncSession) -> int:
        r = await db.execute(select(func.count()).select_from(Document).where(Document.dataset_id == dataset_id))
        return r.scalar() or 0

    @staticmethod
    async def _hit_count(dataset_id: UUID, db: AsyncSession) -> int:
        r = await db.execute(select(func.coalesce(func.sum(Segment.hit_count), 0)).where(Segment.dataset_id == dataset_id))
        return r.scalar() or 0

    @staticmethod
    async def _related_app_count(dataset_id: UUID, db: AsyncSession) -> int:
        r = await db.execute(select(func.count()).select_from(AppDatasetJoin).where(AppDatasetJoin.dataset_id == dataset_id))
        return r.scalar() or 0

    @staticmethod
    async def _character_count(dataset_id: UUID, db: AsyncSession) -> int:
        r = await db.execute(select(func.coalesce(func.sum(Document.character_count), 0)).where(Document.dataset_id == dataset_id))
        return r.scalar() or 0

    @staticmethod
    async def _to_list_item(dataset: Dataset, db: AsyncSession) -> DatasetListItemData:
        return DatasetListItemData(
            id=dataset.id,
            name=dataset.name,
            icon=dataset.icon,
            description=dataset.description,
            document_count=await DatasetService._document_count(dataset.id, db),
            related_app_count=await DatasetService._related_app_count(dataset.id, db),
            character_count=await DatasetService._character_count(dataset.id, db),
            updated_at=int(dataset.updated_at.timestamp()) if dataset.updated_at else 0,
            created_at=int(dataset.created_at.timestamp()) if dataset.created_at else 0,
        )

    @staticmethod
    async def _to_detail(dataset: Dataset, db: AsyncSession) -> DatasetDetailData:
        return DatasetDetailData(
            id=dataset.id,
            name=dataset.name,
            icon=dataset.icon,
            description=dataset.description,
            document_count=await DatasetService._document_count(dataset.id, db),
            hit_count=await DatasetService._hit_count(dataset.id, db),
            related_app_count=await DatasetService._related_app_count(dataset.id, db),
            character_count=await DatasetService._character_count(dataset.id, db),
            updated_at=int(dataset.updated_at.timestamp()) if dataset.updated_at else 0,
            created_at=int(dataset.created_at.timestamp()) if dataset.created_at else 0,
        )

    # ===== hit 检索（5b）=====

    @staticmethod
    async def hit(
        dataset_id: UUID,
        req: HitReq,
        account: Account,
        db: AsyncSession,
        retrieval_service,
    ) -> list[HitRespItem]:
        """召回测试：调 RetrievalService 检索，组装 HitRespItem 列表"""
        # 1.校验知识库权限
        await DatasetService._get_dataset_owned(dataset_id, account, db)

        # 2.执行检索
        lc_documents = await retrieval_service.search_in_datasets(
            dataset_ids=[dataset_id],
            query=req.query,
            account_id=account.id,
            db=db,
            retrieval_strategy=req.retrieval_strategy,
            k=req.k,
            score=req.score,
        )

        if not lc_documents:
            return []

        # 3.查命中的 Segment + Document + UploadFile
        segment_ids = [
            UUID(str(doc.metadata.get("segment_id")))
            for doc in lc_documents
            if doc.metadata.get("segment_id")
        ]
        seg_result = await db.execute(select(Segment).where(Segment.id.in_(segment_ids)))
        segment_dict = {str(seg.id): seg for seg in seg_result.scalars().all()}

        document_ids = list({seg.document_id for seg in segment_dict.values()})
        doc_result = await db.execute(select(Document).where(Document.id.in_(document_ids)))
        document_dict = {str(doc.id): doc for doc in doc_result.scalars().all()}

        upload_file_ids = list({doc.upload_file_id for doc in document_dict.values()})
        uf_result = await db.execute(select(UploadFile).where(UploadFile.id.in_(upload_file_ids)))
        upload_file_dict = {str(uf.id): uf for uf in uf_result.scalars().all()}

        # 4.按检索顺序组装 HitRespItem
        lc_doc_dict = {
            str(doc.metadata.get("segment_id")): doc for doc in lc_documents
        }
        hit_result: list[HitRespItem] = []
        for doc in lc_documents:
            sid = str(doc.metadata.get("segment_id"))
            segment = segment_dict.get(sid)
            if segment is None:
                continue
            document = document_dict.get(str(segment.document_id))
            upload_file = upload_file_dict.get(str(document.upload_file_id)) if document else None

            hit_result.append(HitRespItem(
                id=segment.id,
                document=HitDocumentData(
                    id=document.id if document else segment.document_id,
                    name=document.name if document else "",
                    extension=upload_file.extension if upload_file else "",
                    mime_type=upload_file.mime_type if upload_file else "",
                ),
                dataset_id=segment.dataset_id,
                score=float(lc_doc_dict.get(sid, doc).metadata.get("score", 0.0)),
                position=segment.position,
                content=segment.content,
                keywords=segment.keywords or [],
                character_count=segment.character_count,
                token_count=segment.token_count,
                hit_count=segment.hit_count,
                enabled=segment.enabled,
                disabled_at=int(segment.disabled_at.timestamp()) if segment.disabled_at else 0,
                status=segment.status,
                error=segment.error or "",
                updated_at=int(segment.updated_at.timestamp()) if segment.updated_at else 0,
                created_at=int(segment.created_at.timestamp()) if segment.created_at else 0,
            ))
        return hit_result
