#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Celery 任务：知识库删除（委托 IndexingService）。"""
from __future__ import annotations

from uuid import UUID

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.dataset_task.delete_dataset")
def delete_dataset(dataset_id: str) -> None:
    """删除知识库（5b 实现向量同步部分）"""
    from app.services.indexing_service import IndexingService

    indexing_service = IndexingService()
    indexing_service.delete_dataset(UUID(dataset_id))
