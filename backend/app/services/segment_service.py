#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档片段服务（async，迁移自 imooc segment_service.py）。

Segment CRUD 在请求内**同步**写 Milvus；keyword_table 操作用同步 DB session。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from uuid import UUID

from langchain_core.documents import Document as LCDocument
from redis.asyncio import Redis
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SyncSessionLocal
from app.entities.cache_entity import LOCK_EXPIRE_TIME, LOCK_SEGMENT_UPDATE_ENABLED
from app.entities.dataset_entity import DocumentStatus, SegmentStatus
from app.exceptions import FailException, NotFoundException, ValidateException
from app.lib.helper import generate_text_hash
from app.models.account import Account
from app.models.dataset import Document, Segment
from app.schemas.response import PageData, page_data
from app.schemas.segment import (
    CreateSegmentReq,
    GetSegmentsWithPageReq,
    SegmentDetailData,
    SegmentListItemData,
    UpdateSegmentReq,
)
from app.services.embeddings_service import EmbeddingsService
from app.services.jieba_service import JiebaService
from app.services.keyword_table_service import KeywordTableService
from app.services.vector_database_service import VectorDatabaseService


class SegmentService:
    """文档片段 CRUD 服务（同步写 Milvus）"""

    def __init__(
        self,
        jieba_service: JiebaService,
        embeddings_service: EmbeddingsService,
        keyword_table_service: KeywordTableService,
        vector_database_service: VectorDatabaseService,
    ) -> None:
        self.jieba_service = jieba_service
        self.embeddings_service = embeddings_service
        self.keyword_table_service = keyword_table_service
        self.vector_database_service = vector_database_service

    async def _get_document_owned(
        self, dataset_id: UUID, document_id: UUID, account: Account, db: AsyncSession
    ) -> Document:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None or document.account_id != account.id or document.dataset_id != dataset_id:
            raise NotFoundException("该知识库文档不存在，或无权限，请核实后重试")
        return document

    async def _get_segment_owned(
        self, dataset_id: UUID, document_id: UUID, segment_id: UUID, account: Account, db: AsyncSession
    ) -> Segment:
        result = await db.execute(select(Segment).where(Segment.id == segment_id))
        segment = result.scalar_one_or_none()
        if (
            segment is None
            or segment.account_id != account.id
            or segment.dataset_id != dataset_id
            or segment.document_id != document_id
        ):
            raise NotFoundException("该文档片段不存在，或无权限，请核实后重试")
        return segment

    async def create_segment(
        self,
        dataset_id: UUID,
        document_id: UUID,
        req: CreateSegmentReq,
        account: Account,
        db: AsyncSession,
    ) -> Segment:
        """新增文档片段（同步写 Milvus）"""
        # 1.token 校验
        token_count = EmbeddingsService.calculate_token_count(req.content)
        if token_count > 1000:
            raise ValidateException("片段内容的长度不能超过1000 token")

        # 2.校验文档
        document = await self._get_document_owned(dataset_id, document_id, account, db)
        if document.status != DocumentStatus.COMPLETED:
            raise FailException("当前文档不可新增片段，请稍后尝试")

        # 3.最大位置
        pos_result = await db.execute(
            select(func.coalesce(func.max(Segment.position), 0)).where(Segment.document_id == document_id)
        )
        position = pos_result.scalar() or 0

        # 4.keywords
        keywords = req.keywords
        if not keywords:
            keywords = self.jieba_service.extract_keywords(req.content, 10)

        segment = None
        try:
            position += 1
            segment = Segment(
                account_id=account.id,
                dataset_id=dataset_id,
                document_id=document_id,
                node_id=uuid.uuid4(),
                position=position,
                content=req.content,
                character_count=len(req.content),
                token_count=token_count,
                keywords=keywords,
                hash=generate_text_hash(req.content),
                enabled=True,
                processing_started_at=datetime.now(),
                indexing_completed_at=datetime.now(),
                completed_at=datetime.now(),
                status=SegmentStatus.COMPLETED,
            )
            db.add(segment)
            await db.flush()

            # 5.写 Milvus
            self.vector_database_service.add_documents(
                [LCDocument(
                    page_content=req.content,
                    metadata={
                        "account_id": str(document.account_id),
                        "dataset_id": str(document.dataset_id),
                        "document_id": str(document.id),
                        "segment_id": str(segment.id),
                        "node_id": str(segment.node_id),
                        "document_enabled": document.enabled,
                        "segment_enabled": True,
                    },
                )],
                ids=[str(segment.node_id)],
            )

            # 6.更新文档统计
            stat_result = await db.execute(
                select(
                    func.coalesce(func.sum(Segment.character_count), 0),
                    func.coalesce(func.sum(Segment.token_count), 0),
                ).where(Segment.document_id == document.id)
            )
            doc_char, doc_token = stat_result.one()
            document.character_count = doc_char
            document.token_count = doc_token
            await db.commit()

            # 7.更新关键词表（同步 session）
            if document.enabled is True:
                with SyncSessionLocal() as sync_db:
                    self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [segment.id], sync_db)

        except Exception as e:
            logging.exception("构建文档片段索引发生异常: %s", e)
            if segment is not None:
                segment.error = str(e)
                segment.status = SegmentStatus.ERROR
                segment.enabled = False
                segment.disabled_at = datetime.now()
                segment.stopped_at = datetime.now()
                await db.commit()
            raise FailException("新增文档片段失败，请稍后尝试")

        return segment

    async def update_segment(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
        req: UpdateSegmentReq,
        account: Account,
        db: AsyncSession,
    ) -> Segment:
        """更新文档片段"""
        segment = await self._get_segment_owned(dataset_id, document_id, segment_id, account, db)
        if segment.status != SegmentStatus.COMPLETED:
            raise FailException("当前片段不可修改状态，请稍后尝试")

        keywords = req.keywords
        if not keywords:
            keywords = self.jieba_service.extract_keywords(req.content, 10)

        new_hash = generate_text_hash(req.content)
        required_update = segment.hash != new_hash

        try:
            segment.keywords = keywords
            segment.content = req.content
            segment.hash = new_hash
            segment.character_count = len(req.content)
            segment.token_count = EmbeddingsService.calculate_token_count(req.content)
            await db.commit()

            # 更新关键词表（同步 session）
            with SyncSessionLocal() as sync_db:
                self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id], sync_db)
                self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [segment_id], sync_db)

            if required_update:
                # 更新文档统计
                stat_result = await db.execute(
                    select(
                        func.coalesce(func.sum(Segment.character_count), 0),
                        func.coalesce(func.sum(Segment.token_count), 0),
                    ).where(Segment.document_id == document_id)
                )
                doc_char, doc_token = stat_result.one()
                result = await db.execute(select(Document).where(Document.id == document_id))
                document = result.scalar_one()
                document.character_count = doc_char
                document.token_count = doc_token
                await db.commit()

                # 更新 Milvus text + vector
                vector = self.embeddings_service.embeddings.embed_query(req.content)
                self.vector_database_service.update_by_id(
                    str(segment.node_id),
                    {"text": req.content, "segment_id": str(segment.id), "document_id": str(document_id), "dataset_id": str(dataset_id)},
                    vector=vector,
                )
        except Exception as e:
            logging.exception("更新文档片段记录失败, segment_id: %s, 错误: %s", segment_id, e)
            raise FailException("更新文档片段记录失败，请稍后尝试")

        return segment

    async def get_segments_with_page(
        self,
        dataset_id: UUID,
        document_id: UUID,
        req: GetSegmentsWithPageReq,
        account: Account,
        db: AsyncSession,
    ) -> PageData[SegmentListItemData]:
        """片段分页列表"""
        await self._get_document_owned(dataset_id, document_id, account, db)

        filters = [Segment.document_id == document_id]
        if req.search_word:
            filters.append(Segment.content.ilike(f"%{req.search_word}%"))

        count_result = await db.execute(
            select(func.count()).select_from(Segment).where(*filters)
        )
        total_record = count_result.scalar() or 0

        result = await db.execute(
            select(Segment)
            .where(*filters)
            .order_by(asc(Segment.position))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        segments = result.scalars().all()

        items = [
            SegmentListItemData(
                id=s.id,
                document_id=s.document_id,
                dataset_id=s.dataset_id,
                position=s.position,
                content=s.content,
                keywords=s.keywords or [],
                character_count=s.character_count,
                token_count=s.token_count,
                hit_count=s.hit_count,
                enabled=s.enabled,
                disabled_at=int(s.disabled_at.timestamp()) if s.disabled_at else 0,
                status=s.status,
                error=s.error,
                updated_at=int(s.updated_at.timestamp()) if s.updated_at else 0,
                created_at=int(s.created_at.timestamp()) if s.created_at else 0,
            )
            for s in segments
        ]
        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    async def get_segment_detail(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
        account: Account,
        db: AsyncSession,
    ) -> SegmentDetailData:
        """片段详情"""
        segment = await self._get_segment_owned(dataset_id, document_id, segment_id, account, db)
        return SegmentDetailData(
            id=segment.id,
            document_id=segment.document_id,
            dataset_id=segment.dataset_id,
            position=segment.position,
            content=segment.content,
            keywords=segment.keywords or [],
            character_count=segment.character_count,
            token_count=segment.token_count,
            hit_count=segment.hit_count,
            hash=segment.hash,
            enabled=segment.enabled,
            disabled_at=int(segment.disabled_at.timestamp()) if segment.disabled_at else 0,
            status=segment.status,
            error=segment.error,
            updated_at=int(segment.updated_at.timestamp()) if segment.updated_at else 0,
            created_at=int(segment.created_at.timestamp()) if segment.created_at else 0,
        )

    async def update_segment_enabled(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
        enabled: bool,
        account: Account,
        db: AsyncSession,
        redis: Redis,
    ) -> None:
        """更新片段启用状态（同步更新 Milvus）"""
        segment = await self._get_segment_owned(dataset_id, document_id, segment_id, account, db)
        if segment.status != SegmentStatus.COMPLETED:
            raise FailException("当前片段不可修改状态，请稍后尝试")
        if enabled == segment.enabled:
            raise FailException(f"片段状态修改错误，当前已是{'启用' if enabled else '禁用'}")

        cache_key = LOCK_SEGMENT_UPDATE_ENABLED.format(segment_id=segment_id)
        if await redis.get(cache_key) is not None:
            raise FailException("当前文档片段正在修改状态，请稍后尝试")

        try:
            segment.enabled = enabled
            segment.disabled_at = None if enabled else datetime.now()
            await db.commit()

            # 更新关键词表（同步 session）
            result = await db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one()
            with SyncSessionLocal() as sync_db:
                if enabled is True and document.enabled is True:
                    self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [segment_id], sync_db)
                else:
                    self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id], sync_db)

            # 同步 Milvus segment_enabled
            self.vector_database_service.update_by_id(
                str(segment.node_id),
                {"segment_enabled": enabled},
            )
        except Exception as e:
            logging.exception("更改片段启用状态异常, segment_id: %s, 错误: %s", segment_id, e)
            segment.error = str(e)
            segment.status = SegmentStatus.ERROR
            segment.enabled = False
            segment.disabled_at = datetime.now()
            segment.stopped_at = datetime.now()
            await db.commit()
            raise FailException("更新文档片段启用状态失败，请稍后重试")

    async def delete_segment(
        self,
        dataset_id: UUID,
        document_id: UUID,
        segment_id: UUID,
        account: Account,
        db: AsyncSession,
    ) -> None:
        """删除片段（同步删 Milvus + keyword_table）"""
        segment = await self._get_segment_owned(dataset_id, document_id, segment_id, account, db)
        if segment.status not in [SegmentStatus.COMPLETED, SegmentStatus.ERROR]:
            raise FailException("当前文档片段处于不可删除状态，请稍后尝试")

        await db.delete(segment)
        await db.commit()

        # 删关键词表（同步 session）
        with SyncSessionLocal() as sync_db:
            self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id], sync_db)

        # 删 Milvus
        try:
            self.vector_database_service.delete_by_id(str(segment.node_id))
        except Exception as e:
            logging.exception("删除片段向量失败, segment_id: %s, 错误: %s", segment_id, e)

        # 更新文档统计
        stat_result = await db.execute(
            select(
                func.coalesce(func.sum(Segment.character_count), 0),
                func.coalesce(func.sum(Segment.token_count), 0),
            ).where(Segment.document_id == document_id)
        )
        doc_char, doc_token = stat_result.one()
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one()
        document.character_count = doc_char
        document.token_count = doc_token
        await db.commit()
