#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档索引构建服务（Celery 任务内同步执行）。

迁移自 imooc indexing_service.py。build_documents 为 5a 完整实现；
update_document_enabled / delete_document / delete_dataset 的向量同步部分归 5b，此处仅删 PG。
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from uuid import UUID

from langchain_core.documents import Document as LCDocument
from minio import Minio
from pymilvus import MilvusClient
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.file_extractor import FileExtractor
from app.db import SyncSessionLocal
from app.entities.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED
from app.entities.dataset_entity import DocumentStatus, SegmentStatus
from app.exceptions import NotFoundException
from app.lib.helper import generate_text_hash
from app.models.dataset import DatasetQuery, Document, KeywordTable, Segment
from app.services.embeddings_service import EmbeddingsService
from app.services.jieba_service import JiebaService
from app.services.keyword_table_service import KeywordTableService
from app.services.process_rule_service import ProcessRuleService
from app.services.vector_database_service import VectorDatabaseService


def _sync_redis() -> Redis:
    return Redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


def _milvus_client() -> MilvusClient:
    return MilvusClient(uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}")


def _minio_client() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        secure=False,
    )


class IndexingService:
    """文档索引构建服务（Celery 同步执行）"""

    def __init__(self) -> None:
        self.redis_client = _sync_redis()
        self.minio_client = _minio_client()
        self.file_extractor = FileExtractor(self.minio_client)
        self.jieba_service = JiebaService()
        self.embeddings_service = EmbeddingsService(self.redis_client)
        self.keyword_table_service = KeywordTableService(self.redis_client)
        self.vector_database_service = VectorDatabaseService(
            _milvus_client(), self.embeddings_service
        )

    # ===== build_documents（5a 完整实现）=====

    def build_documents(self, document_ids: list[UUID]) -> None:
        """构建文档：解析 → 分片 → embedding → 写 Milvus"""
        with SyncSessionLocal() as db:
            documents = db.execute(
                select(Document).where(Document.id.in_(document_ids))
            ).scalars().all()

            for document in documents:
                try:
                    document.status = DocumentStatus.PARSING
                    document.processing_started_at = datetime.now()
                    db.commit()

                    lc_documents = self._parsing(document, db)
                    lc_segments = self._splitting(document, lc_documents, db)
                    self._indexing(document, lc_segments, db)
                    self._completed(document, lc_segments, db)
                except Exception as e:
                    logging.exception("构建文档发生错误: %s", e)
                    document.status = DocumentStatus.ERROR
                    document.error = str(e)
                    document.stopped_at = datetime.now()
                    db.commit()

    def _parsing(self, document: Document, db: Session) -> list[LCDocument]:
        """解析文档为 LangChain 文档列表"""
        # 查 upload_file
        from app.models.upload_file import UploadFile
        upload_file = db.execute(
            select(UploadFile).where(UploadFile.id == document.upload_file_id)
        ).scalar_one_or_none()
        if upload_file is None:
            raise NotFoundException("上传文件不存在")

        lc_documents = self.file_extractor.load(upload_file, False, True)
        for lc_document in lc_documents:
            lc_document.page_content = self._clean_extra_text(lc_document.page_content)

        document.character_count = sum(len(d.page_content) for d in lc_documents)
        document.status = DocumentStatus.SPLITTING
        document.parsing_completed_at = datetime.now()
        db.commit()
        return lc_documents

    def _splitting(
        self, document: Document, lc_documents: list[LCDocument], db: Session
    ) -> list[LCDocument]:
        """分割文档为片段"""
        from app.models.dataset import ProcessRule
        process_rule = db.execute(
            select(ProcessRule).where(ProcessRule.id == document.process_rule_id)
        ).scalar_one_or_none()
        if process_rule is None:
            raise NotFoundException("处理规则不存在")

        text_splitter = ProcessRuleService.get_text_splitter_by_process_rule(
            process_rule, EmbeddingsService.calculate_token_count
        )

        for lc_document in lc_documents:
            lc_document.page_content = ProcessRuleService.clean_text_by_process_rule(
                lc_document.page_content, process_rule
            )

        lc_segments = text_splitter.split_documents(lc_documents)

        position = db.execute(
            select(func.coalesce(func.max(Segment.position), 0)).where(Segment.document_id == document.id)
        ).scalar() or 0

        for lc_segment in lc_segments:
            position += 1
            content = lc_segment.page_content
            segment = Segment(
                account_id=document.account_id,
                dataset_id=document.dataset_id,
                document_id=document.id,
                node_id=uuid.uuid4(),
                position=position,
                content=content,
                character_count=len(content),
                token_count=EmbeddingsService.calculate_token_count(content),
                hash=generate_text_hash(content),
                status=SegmentStatus.WAITING,
            )
            db.add(segment)
            db.flush()
            lc_segment.metadata = {
                "account_id": str(document.account_id),
                "dataset_id": str(document.dataset_id),
                "document_id": str(document.id),
                "segment_id": str(segment.id),
                "node_id": str(segment.node_id),
                "document_enabled": False,
                "segment_enabled": False,
            }

        document.token_count = sum(
            EmbeddingsService.calculate_token_count(s.page_content) for s in lc_segments
        )
        document.status = DocumentStatus.INDEXING
        document.splitting_completed_at = datetime.now()
        db.commit()
        return lc_segments

    def _indexing(
        self, document: Document, lc_segments: list[LCDocument], db: Session
    ) -> None:
        """构建索引：关键词提取 + 词表构建"""
        for lc_segment in lc_segments:
            keywords = self.jieba_service.extract_keywords(lc_segment.page_content, 10)

            segment_id = lc_segment.metadata["segment_id"]
            db.execute(
                select(Segment).where(Segment.id == segment_id)
            )
            from sqlalchemy import update as sa_update
            db.execute(
                sa_update(Segment).where(Segment.id == segment_id).values(
                    keywords=keywords,
                    status=SegmentStatus.INDEXING,
                    indexing_completed_at=datetime.now(),
                )
            )
            db.commit()

            keyword_table_record = self.keyword_table_service.get_keyword_table_from_dataset_id(
                document.dataset_id, db
            )
            keyword_table = {
                field: set(value) for field, value in keyword_table_record.keyword_table.items()
            }
            for keyword in keywords:
                if keyword not in keyword_table:
                    keyword_table[keyword] = set()
                keyword_table[keyword].add(lc_segment.metadata["segment_id"])
            keyword_table_record.keyword_table = {
                field: list(value) for field, value in keyword_table.items()
            }
            db.commit()

        document.indexing_completed_at = datetime.now()
        db.commit()

    def _completed(
        self, document: Document, lc_segments: list[LCDocument], db: Session
    ) -> None:
        """存储片段到 Milvus，并完成状态更新"""
        for lc_segment in lc_segments:
            lc_segment.metadata["document_enabled"] = True
            lc_segment.metadata["segment_enabled"] = True

        from sqlalchemy import update as sa_update
        try:
            for i in range(0, len(lc_segments), 10):
                chunks = lc_segments[i:i + 10]
                ids = [chunk.metadata["node_id"] for chunk in chunks]
                self.vector_database_service.add_documents(chunks, ids=ids)
                db.execute(
                    sa_update(Segment).where(Segment.node_id.in_(ids)).values(
                        status=SegmentStatus.COMPLETED,
                        completed_at=datetime.now(),
                        enabled=True,
                    )
                )
                db.commit()
        except Exception as e:
            logging.exception("构建文档片段索引发生异常: %s", e)
            db.execute(
                sa_update(Segment).where(Segment.node_id.in_(ids)).values(
                    status=SegmentStatus.ERROR,
                    completed_at=None,
                    stopped_at=datetime.now(),
                    enabled=False,
                    error=str(e),
                )
            )
            db.commit()
            raise

        document.status = DocumentStatus.COMPLETED
        document.completed_at = datetime.now()
        document.enabled = True
        db.commit()

    @classmethod
    def _clean_extra_text(cls, text: str) -> str:
        """清除过滤多余空白字符串"""
        text = re.sub(r"<\|", "<", text)
        text = re.sub(r"\|>", ">", text)
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xEF\xBF\xBE]", "", text)
        text = re.sub("\uFFFE", "", text)
        return text

    # ===== 5b：向量同步部分 =====

    def update_document_enabled(self, document_id: UUID) -> None:
        """更新文档启用状态：同步 Milvus document_enabled + keyword_table"""
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document_id)
        try:
            with SyncSessionLocal() as db:
                document = db.execute(
                    select(Document).where(Document.id == document_id)
                ).scalar_one_or_none()
                if document is None:
                    raise NotFoundException("当前文档不存在")

                # 1.查该文档下所有 COMPLETED 片段（id, node_id, enabled）
                seg_rows = db.execute(
                    select(Segment.id, Segment.node_id, Segment.enabled).where(
                        Segment.document_id == document_id,
                        Segment.status == SegmentStatus.COMPLETED,
                    )
                ).all()
                segment_ids = [row[0] for row in seg_rows]
                node_ids = [str(row[1]) for row in seg_rows]

                # 2.逐个更新 Milvus document_enabled，单 node 失败标记该 Segment ERROR
                for seg_id, node_id, _enabled in seg_rows:
                    try:
                        self.vector_database_service.update_by_id(
                            str(node_id),
                            {"document_enabled": document.enabled},
                        )
                    except Exception as e:
                        logging.exception(
                            "更新片段向量启用状态失败, node_id: %s, 错误: %s", node_id, e
                        )
                        db.execute(
                            update(Segment).where(Segment.id == seg_id).values(
                                error=str(e),
                                status=SegmentStatus.ERROR,
                                enabled=False,
                                disabled_at=datetime.now(),
                                stopped_at=datetime.now(),
                            )
                        )
                        db.commit()

                # 3.同步关键词表
                try:
                    if document.enabled is True:
                        enabled_segment_ids = [row[0] for row in seg_rows if row[2] is True]
                        if enabled_segment_ids:
                            self.keyword_table_service.add_keyword_table_from_ids(
                                document.dataset_id, enabled_segment_ids, db
                            )
                    else:
                        if segment_ids:
                            self.keyword_table_service.delete_keyword_table_from_ids(
                                document.dataset_id, segment_ids, db
                            )
                except Exception as e:
                    logging.exception("同步关键词表失败, document_id: %s, 错误: %s", document_id, e)
        except Exception as e:
            logging.exception(
                "修改向量数据库文档启用状态失败, document_id: %s, 错误: %s", document_id, e
            )
            # 回滚 document.enabled
            try:
                with SyncSessionLocal() as db:
                    document = db.execute(
                        select(Document).where(Document.id == document_id)
                    ).scalar_one_or_none()
                    if document is not None:
                        origin_enabled = not document.enabled
                        document.enabled = origin_enabled
                        document.disabled_at = None if origin_enabled else datetime.now()
                        db.commit()
            except Exception:
                logging.exception("回滚 document.enabled 失败, document_id: %s", document_id)
        finally:
            self.redis_client.delete(cache_key)

    def delete_document(self, dataset_id: UUID, document_id: UUID) -> None:
        """删除文档：删 Milvus + 删 PG Segment + 删关键词表"""
        with SyncSessionLocal() as db:
            from sqlalchemy import delete as sa_delete
            # 1.查该文档所有 segment_id
            seg_rows = db.execute(
                select(Segment.id).where(Segment.document_id == document_id)
            ).all()
            segment_ids = [row[0] for row in seg_rows]

            # 2.删 Milvus（按 document_id）
            try:
                self.vector_database_service.delete_by_document_id(str(document_id))
            except Exception as e:
                logging.exception("删除文档向量失败, document_id: %s, 错误: %s", document_id, e)

            # 3.删 PG Segment（Document 记录已由 DocumentService 同步删除）
            db.execute(sa_delete(Segment).where(Segment.document_id == document_id))
            db.commit()

            # 4.删关键词表
            if segment_ids:
                try:
                    self.keyword_table_service.delete_keyword_table_from_ids(
                        dataset_id, segment_ids, db
                    )
                except Exception as e:
                    logging.exception("删除关键词表失败, dataset_id: %s, 错误: %s", dataset_id, e)

    def delete_dataset(self, dataset_id: UUID) -> None:
        """删除知识库：删 PG 关联表 + 删 Milvus"""
        try:
            with SyncSessionLocal() as db:
                from sqlalchemy import delete as sa_delete
                db.execute(sa_delete(Document).where(Document.dataset_id == dataset_id))
                db.execute(sa_delete(Segment).where(Segment.dataset_id == dataset_id))
                db.execute(sa_delete(KeywordTable).where(KeywordTable.dataset_id == dataset_id))
                db.execute(sa_delete(DatasetQuery).where(DatasetQuery.dataset_id == dataset_id))
                db.commit()

            # 删 Milvus（按 dataset_id）
            try:
                self.vector_database_service.delete_by_dataset_id(str(dataset_id))
            except Exception as e:
                logging.exception("删除知识库向量失败, dataset_id: %s, 错误: %s", dataset_id, e)
        except Exception as e:
            logging.exception("异步删除知识库关联内容出错, dataset_id: %s, 错误: %s", dataset_id, e)
