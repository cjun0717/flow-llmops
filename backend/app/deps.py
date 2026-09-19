#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""基础设施组件依赖：DB / Redis / MinIO / LanguageModelManager / Milvus / Embeddings / Segment。"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Annotated
from fastapi import Depends
from minio import Minio
from pymilvus import MilvusClient
from redis import Redis as SyncRedis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.language_model import LanguageModelManager
from app.db import AsyncSessionLocal
from app.services.embeddings_service import EmbeddingsService
from app.services.jieba_service import JiebaService
from app.services.keyword_table_service import KeywordTableService
from app.services.language_model_service import LanguageModelService
from app.services.retrieval_service import RetrievalService
from app.services.segment_service import SegmentService
from app.services.vector_database_service import VectorDatabaseService

_redis_client: Redis | None = None
_minio_client: Minio | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis() -> Redis:
    """获取 Redis 客户端（进程内单例）"""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 连接（应用关闭时调用）"""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def get_minio_client() -> Minio:
    """获取 MinIO 客户端（进程内单例）"""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=False,
        )
    return _minio_client


# 数据库
AsyncSessionDep = Annotated[AsyncSession, Depends(get_db)]

# redis
RedisDep = Annotated[Redis, Depends(get_redis)]

# minio
MinioDep = Annotated[Minio, Depends(get_minio_client)]


@lru_cache
def get_language_model_manager() -> LanguageModelManager:
    """获取语言模型管理器（进程内单例，构造时读 yaml）"""
    return LanguageModelManager()


def get_language_model_service(
    manager: LanguageModelManager = Depends(get_language_model_manager),
) -> LanguageModelService:
    """获取语言模型服务"""
    return LanguageModelService(manager)


# 语言模型
LanguageModelServiceDep = Annotated[LanguageModelService, Depends(get_language_model_service)]


# ===== 知识库相关依赖 =====

_sync_redis_client: SyncRedis | None = None


def get_sync_redis() -> SyncRedis:
    """获取同步 Redis 客户端（进程内单例，供 keyword_table 锁用）"""
    global _sync_redis_client
    if _sync_redis_client is None:
        _sync_redis_client = SyncRedis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _sync_redis_client


@lru_cache
def get_milvus_client() -> MilvusClient:
    """获取 Milvus 客户端（进程内单例）"""
    return MilvusClient(uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}")


@lru_cache
def get_embeddings_service() -> EmbeddingsService:
    """获取 Embeddings 服务（进程内单例）"""
    return EmbeddingsService(get_sync_redis())


@lru_cache
def get_jieba_service() -> JiebaService:
    """获取 Jieba 服务（进程内单例）"""
    return JiebaService()


@lru_cache
def get_keyword_table_service() -> KeywordTableService:
    """获取 KeywordTable 服务（进程内单例）"""
    return KeywordTableService(get_sync_redis())


@lru_cache
def get_vector_database_service() -> VectorDatabaseService:
    """获取向量数据库服务（进程内单例）"""
    return VectorDatabaseService(get_milvus_client(), get_embeddings_service())


def get_segment_service(
    jieba: JiebaService = Depends(get_jieba_service),
    embeddings: EmbeddingsService = Depends(get_embeddings_service),
    keyword_table: KeywordTableService = Depends(get_keyword_table_service),
    vector_db: VectorDatabaseService = Depends(get_vector_database_service),
) -> SegmentService:
    """获取片段服务"""
    return SegmentService(jieba, embeddings, keyword_table, vector_db)


SegmentServiceDep = Annotated[SegmentService, Depends(get_segment_service)]


def get_retrieval_service(
    jieba: JiebaService = Depends(get_jieba_service),
    vector_db: VectorDatabaseService = Depends(get_vector_database_service),
) -> RetrievalService:
    """获取检索服务"""
    return RetrievalService(jieba, vector_db)


RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]