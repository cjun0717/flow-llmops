#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按知识库绑定的向量模型构造 Embeddings + Milvus collection。"""
from __future__ import annotations

from uuid import UUID

from pymilvus import MilvusClient
from redis import Redis
from sqlalchemy.orm import Session

from app.exceptions import NotFoundException
from app.models.dataset import Dataset
from app.services.embeddings_service import EmbeddingsService
from app.services.user_model_service import UserModelService
from app.services.vector_database_service import VectorDatabaseService


def vector_stack_for_dataset(
    dataset: Dataset,
    redis: Redis | None,
    milvus_client: MilvusClient,
    sync_db: Session,
) -> tuple[EmbeddingsService, VectorDatabaseService]:
    """根据知识库绑定（或账号默认）向量模型构造运行时栈。"""
    record = UserModelService.resolve_embedding_sync(dataset, sync_db)
    embeddings = EmbeddingsService.from_user_model(record, redis)
    vdb = VectorDatabaseService(milvus_client, embeddings, record.dimension)
    return embeddings, vdb


def vector_stack_for_dataset_id(
    dataset_id: UUID,
    redis: Redis | None,
    milvus_client: MilvusClient,
    sync_db: Session,
) -> tuple[EmbeddingsService, VectorDatabaseService]:
    dataset = sync_db.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundException("该知识库不存在")
    return vector_stack_for_dataset(dataset, redis, milvus_client, sync_db)
