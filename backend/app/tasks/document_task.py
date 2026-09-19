#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Celery 任务：文档构建/启停/删除（委托 IndexingService）。"""
from __future__ import annotations

from uuid import UUID

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.document_task.build_documents")
def build_documents(document_ids: list[str]) -> None:
    """构建文档：解析 → 分片 → embedding → 写 Milvus"""
    from app.services.indexing_service import IndexingService

    indexing_service = IndexingService()
    indexing_service.build_documents([UUID(did) for did in document_ids])


@celery_app.task(name="app.tasks.document_task.update_document_enabled")
def update_document_enabled(document_id: str) -> None:
    """更新文档启用状态（5b 实现向量同步部分）"""
    from app.services.indexing_service import IndexingService

    indexing_service = IndexingService()
    indexing_service.update_document_enabled(UUID(document_id))


@celery_app.task(name="app.tasks.document_task.delete_document")
def delete_document(dataset_id: str, document_id: str) -> None:
    """删除文档（5b 实现向量同步部分）"""
    from app.services.indexing_service import IndexingService

    indexing_service = IndexingService()
    indexing_service.delete_document(UUID(dataset_id), UUID(document_id))
