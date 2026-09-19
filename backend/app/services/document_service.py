#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档服务（async，迁移自 imooc document_service.py）。"""
from __future__ import annotations

import random
import time
from datetime import datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED, LOCK_EXPIRE_TIME
from app.entities.dataset_entity import DocumentStatus, ProcessType, SegmentStatus
from app.exceptions import FailException, ForbiddenException, NotFoundException
from app.lib.helper import datetime_to_timestamp
from app.models.account import Account
from app.models.dataset import Dataset, Document, ProcessRule, Segment
from app.models.upload_file import UploadFile
from app.schemas.document import (
    CreateDocumentsReq,
    DocumentDetailData,
    DocumentListItemData,
    GetDocumentsWithPageReq,
)
from app.schemas.response import PageData, page_data
from app.services.upload_file_service import ALLOWED_DOCUMENT_EXTENSION


class DocumentService:
    """文档 CRUD 服务"""

    @staticmethod
    async def _check_dataset(dataset_id: UUID, account: Account, db: AsyncSession) -> Dataset:
        """校验知识库权限"""
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if dataset is None or dataset.account_id != account.id:
            raise ForbiddenException("当前用户无该知识库权限或知识库不存在")
        return dataset

    @staticmethod
    async def _get_document_owned(
        dataset_id: UUID, document_id: UUID, account: Account, db: AsyncSession
    ) -> Document:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            raise NotFoundException("该文档不存在，请核实后重试")
        if document.dataset_id != dataset_id or document.account_id != account.id:
            raise ForbiddenException("当前用户无权限访问该文档，请核实后重试")
        return document

    @staticmethod
    async def create_documents(
        dataset_id: UUID,
        req: CreateDocumentsReq,
        account: Account,
        db: AsyncSession,
    ) -> tuple[list[Document], str]:
        """创建文档列表并触发异步构建任务"""
        # 1.校验知识库权限
        await DocumentService._check_dataset(dataset_id, account, db)

        # 2.提取上传文件并校验扩展名
        result = await db.execute(
            select(UploadFile).where(
                UploadFile.account_id == account.id,
                UploadFile.id.in_(req.upload_file_ids),
            )
        )
        upload_files = [
            f for f in result.scalars().all()
            if f.extension.lower() in ALLOWED_DOCUMENT_EXTENSION
        ]
        if not upload_files:
            raise FailException("暂未解析到合法文件，请重新上传")

        # 3.创建批次与处理规则
        batch = time.strftime("%Y%m%d%H%M%S") + str(random.randint(100000, 999999))
        process_rule = ProcessRule(
            account_id=account.id,
            dataset_id=dataset_id,
            mode=req.process_type.value,
            rule=req.rule,
        )
        db.add(process_rule)
        await db.flush()

        # 4.获取最新文档位置
        position = await DocumentService._get_latest_document_position(dataset_id, db)

        # 5.创建文档记录
        documents: list[Document] = []
        for upload_file in upload_files:
            position += 1
            document = Document(
                account_id=account.id,
                dataset_id=dataset_id,
                upload_file_id=upload_file.id,
                process_rule_id=process_rule.id,
                batch=batch,
                name=upload_file.name,
                position=position,
            )
            db.add(document)
            documents.append(document)
        await db.commit()
        for d in documents:
            await db.refresh(d)

        # 6.触发异步构建任务
        from app.tasks.document_task import build_documents
        build_documents.delay([str(d.id) for d in documents])

        return documents, batch

    @staticmethod
    async def get_documents_with_page(
        dataset_id: UUID,
        req: GetDocumentsWithPageReq,
        account: Account,
        db: AsyncSession,
    ) -> PageData[DocumentListItemData]:
        """文档分页列表"""
        await DocumentService._check_dataset(dataset_id, account, db)

        filters = [Document.account_id == account.id, Document.dataset_id == dataset_id]
        if req.search_word:
            filters.append(Document.name.ilike(f"%{req.search_word}%"))

        count_result = await db.execute(
            select(func.count()).select_from(Document).where(*filters)
        )
        total_record = count_result.scalar() or 0

        result = await db.execute(
            select(Document)
            .where(*filters)
            .order_by(desc(Document.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        documents = result.scalars().all()

        items = []
        for doc in documents:
            hit_count = await DocumentService._doc_hit_count(doc.id, db)
            items.append(DocumentListItemData(
                id=doc.id,
                name=doc.name,
                character_count=doc.character_count,
                hit_count=hit_count,
                position=doc.position,
                enabled=doc.enabled,
                disabled_at=datetime_to_timestamp(doc.disabled_at),
                status=doc.status,
                error=doc.error,
                updated_at=datetime_to_timestamp(doc.updated_at),
                created_at=datetime_to_timestamp(doc.created_at),
            ))
        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @staticmethod
    async def get_document_detail(
        dataset_id: UUID, document_id: UUID, account: Account, db: AsyncSession
    ) -> DocumentDetailData:
        """文档详情"""
        document = await DocumentService._get_document_owned(dataset_id, document_id, account, db)
        segment_count = await DocumentService._doc_segment_count(document.id, db)
        hit_count = await DocumentService._doc_hit_count(document.id, db)
        return DocumentDetailData(
            id=document.id,
            dataset_id=document.dataset_id,
            name=document.name,
            segment_count=segment_count,
            character_count=document.character_count,
            hit_count=hit_count,
            position=document.position,
            enabled=document.enabled,
            disabled_at=datetime_to_timestamp(document.disabled_at),
            status=document.status,
            error=document.error,
            updated_at=datetime_to_timestamp(document.updated_at),
            created_at=datetime_to_timestamp(document.created_at),
        )

    @staticmethod
    async def update_document_name(
        dataset_id: UUID, document_id: UUID, name: str, account: Account, db: AsyncSession
    ) -> None:
        """更新文档名称"""
        document = await DocumentService._get_document_owned(dataset_id, document_id, account, db)
        document.name = name
        await db.commit()

    @staticmethod
    async def update_document_enabled(
        dataset_id: UUID,
        document_id: UUID,
        enabled: bool,
        account: Account,
        db: AsyncSession,
        redis: Redis,
    ) -> None:
        """更新文档启用状态（触发 Celery 同步向量）"""
        document = await DocumentService._get_document_owned(dataset_id, document_id, account, db)

        if document.status != DocumentStatus.COMPLETED:
            raise ForbiddenException("当前文档处于不可修改状态，请稍后重试")
        if document.enabled == enabled:
            raise FailException(f"文档状态修改错误，当前已是{'启用' if enabled else '禁用'}状态")

        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document.id)
        if await redis.get(cache_key) is not None:
            raise FailException("当前文档正在修改启用状态，请稍后再次尝试")

        document.enabled = enabled
        document.disabled_at = None if enabled else datetime.now()
        await db.commit()
        await redis.setex(cache_key, LOCK_EXPIRE_TIME, 1)

        from app.tasks.document_task import update_document_enabled as update_task
        update_task.delay(str(document.id))

    @staticmethod
    async def delete_document(
        dataset_id: UUID, document_id: UUID, account: Account, db: AsyncSession
    ) -> None:
        """删除文档（删 PG + 触发 Celery 删向量）"""
        document = await DocumentService._get_document_owned(dataset_id, document_id, account, db)
        if document.status not in [DocumentStatus.COMPLETED, DocumentStatus.ERROR]:
            raise FailException("当前文档处于不可删除状态，请稍后重试")

        await db.delete(document)
        await db.commit()

        from app.tasks.document_task import delete_document as delete_task
        delete_task.delay(str(dataset_id), str(document_id))

    @staticmethod
    async def get_documents_status(
        dataset_id: UUID, batch: str, account: Account, db: AsyncSession
    ) -> list[dict]:
        """获取批次文档处理状态"""
        await DocumentService._check_dataset(dataset_id, account, db)

        result = await db.execute(
            select(Document)
            .where(Document.dataset_id == dataset_id, Document.batch == batch)
            .order_by(asc(Document.position))
        )
        documents = result.scalars().all()
        if not documents:
            raise NotFoundException("该处理批次未发现文档，请核实后重试")

        status_list: list[dict] = []
        for document in documents:
            segment_count = await DocumentService._doc_segment_count(document.id, db)
            completed_result = await db.execute(
                select(func.count()).select_from(Segment).where(
                    Segment.document_id == document.id,
                    Segment.status == SegmentStatus.COMPLETED,
                )
            )
            completed_segment_count = completed_result.scalar() or 0

            # 查 upload_file
            uf_result = await db.execute(select(UploadFile).where(UploadFile.id == document.upload_file_id))
            upload_file = uf_result.scalar_one_or_none()

            status_list.append({
                "id": document.id,
                "name": document.name,
                "size": upload_file.size if upload_file else 0,
                "extension": upload_file.extension if upload_file else "",
                "mime_type": upload_file.mime_type if upload_file else "",
                "position": document.position,
                "segment_count": segment_count,
                "completed_segment_count": completed_segment_count,
                "error": document.error,
                "status": document.status,
                "processing_started_at": datetime_to_timestamp(document.processing_started_at),
                "parsing_completed_at": datetime_to_timestamp(document.parsing_completed_at),
                "splitting_completed_at": datetime_to_timestamp(document.splitting_completed_at),
                "indexing_completed_at": datetime_to_timestamp(document.indexing_completed_at),
                "completed_at": datetime_to_timestamp(document.completed_at),
                "stopped_at": datetime_to_timestamp(document.stopped_at),
                "created_at": datetime_to_timestamp(document.created_at),
            })
        return status_list

    @staticmethod
    async def _get_latest_document_position(dataset_id: UUID, db: AsyncSession) -> int:
        result = await db.execute(
            select(Document).where(Document.dataset_id == dataset_id).order_by(desc(Document.position)).limit(1)
        )
        document = result.scalar_one_or_none()
        return document.position if document else 0

    @staticmethod
    async def _doc_segment_count(document_id: UUID, db: AsyncSession) -> int:
        r = await db.execute(select(func.count()).select_from(Segment).where(Segment.document_id == document_id))
        return r.scalar() or 0

    @staticmethod
    async def _doc_hit_count(document_id: UUID, db: AsyncSession) -> int:
        r = await db.execute(select(func.coalesce(func.sum(Segment.hit_count), 0)).where(Segment.document_id == document_id))
        return r.scalar() or 0
