#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""基础设施组件依赖：DB / Redis / MinIO / LanguageModelManager。"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Annotated
from fastapi import Depends
from minio import Minio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.language_model import LanguageModelManager
from app.db import AsyncSessionLocal
from app.services.language_model_service import LanguageModelService

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