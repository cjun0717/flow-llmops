#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""基础设施组件依赖：DB / Redis / MinIO / Milvus / Segment。"""
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
from app.db import AsyncSessionLocal
from app.services.jieba_service import JiebaService
from app.services.keyword_table_service import KeywordTableService
from app.services.language_model_service import LanguageModelService
from app.services.retrieval_service import RetrievalService
from app.services.segment_service import SegmentService
from app.services.api_tool_service import ApiToolService
from app.services.app_config_service import AppConfigService
from app.services.builtin_tool_service import BuiltinToolService
from app.services.mcp_tool_service import McpToolService
from app.core.tools.api_tools.providers import ApiProviderManager
from app.core.tools.builtin_tools.categories import BuiltinCategoryManager
from app.core.tools.builtin_tools.providers import BuiltinProviderManager
from app.core.tools.mcp_tools.providers import McpProviderManager
from app.core.builtin_apps import BuiltinAppManager
from app.services.assistant_knowledge_service import AssistantKnowledgeService

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


def get_language_model_service() -> LanguageModelService:
    """获取语言模型服务"""
    return LanguageModelService()


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


# 同步 redis（供 Agent 队列管理器在子线程中使用）
SyncRedisDep = Annotated[SyncRedis, Depends(get_sync_redis)]


@lru_cache
def get_milvus_client() -> MilvusClient:
    """获取 Milvus 客户端（进程内单例）"""
    return MilvusClient(uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}")


@lru_cache
def get_jieba_service() -> JiebaService:
    """获取 Jieba 服务（进程内单例）"""
    return JiebaService()


@lru_cache
def get_keyword_table_service() -> KeywordTableService:
    """获取 KeywordTable 服务（进程内单例）"""
    return KeywordTableService(get_sync_redis())


def get_segment_service(
    jieba: JiebaService = Depends(get_jieba_service),
    keyword_table: KeywordTableService = Depends(get_keyword_table_service),
) -> SegmentService:
    """获取片段服务"""
    return SegmentService(jieba, keyword_table)


SegmentServiceDep = Annotated[SegmentService, Depends(get_segment_service)]


def get_retrieval_service(
    jieba: JiebaService = Depends(get_jieba_service),
) -> RetrievalService:
    """获取检索服务"""
    return RetrievalService(jieba)


RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]


# ===== 阶段6 插件相关依赖 =====


@lru_cache
def get_builtin_provider_manager() -> BuiltinProviderManager:
    """获取内置工具提供商管理器（进程内单例）"""
    return BuiltinProviderManager()


@lru_cache
def get_builtin_category_manager() -> BuiltinCategoryManager:
    """获取内置工具分类管理器（进程内单例）"""
    return BuiltinCategoryManager()


@lru_cache
def get_api_provider_manager() -> ApiProviderManager:
    """获取 API 工具提供者管理器（进程内单例）"""
    return ApiProviderManager()


@lru_cache
def get_mcp_provider_manager() -> McpProviderManager:
    """获取 MCP 工具提供者管理器（进程内单例）"""
    return McpProviderManager()


def get_builtin_tool_service(
    builtin_provider_manager: BuiltinProviderManager = Depends(get_builtin_provider_manager),
    builtin_category_manager: BuiltinCategoryManager = Depends(get_builtin_category_manager),
) -> BuiltinToolService:
    """获取内置工具服务"""
    return BuiltinToolService(builtin_provider_manager, builtin_category_manager)


BuiltinToolServiceDep = Annotated[BuiltinToolService, Depends(get_builtin_tool_service)]


def get_api_tool_service(
    api_provider_manager: ApiProviderManager = Depends(get_api_provider_manager),
) -> ApiToolService:
    """获取 API 工具服务"""
    return ApiToolService()


ApiToolServiceDep = Annotated[ApiToolService, Depends(get_api_tool_service)]


def get_mcp_tool_service(
    mcp_provider_manager: McpProviderManager = Depends(get_mcp_provider_manager),
) -> McpToolService:
    """获取 MCP 工具服务"""
    return McpToolService(mcp_provider_manager)


McpToolServiceDep = Annotated[McpToolService, Depends(get_mcp_tool_service)]


def get_app_config_service(
    api_provider_manager: ApiProviderManager = Depends(get_api_provider_manager),
    mcp_provider_manager: McpProviderManager = Depends(get_mcp_provider_manager),
    builtin_provider_manager: BuiltinProviderManager = Depends(get_builtin_provider_manager),
) -> AppConfigService:
    """获取应用配置服务"""
    return AppConfigService(
        api_provider_manager,
        mcp_provider_manager,
        builtin_provider_manager,
    )


AppConfigServiceDep = Annotated[AppConfigService, Depends(get_app_config_service)]


# ===== 阶段11 应用广场 =====


@lru_cache
def get_builtin_app_manager() -> BuiltinAppManager:
    """获取内置应用管理器（进程内单例，构造时读 yaml）"""
    return BuiltinAppManager()


BuiltinAppManagerDep = Annotated[BuiltinAppManager, Depends(get_builtin_app_manager)]


# ===== 阶段11.3 辅助 Agent =====


@lru_cache
def get_assistant_knowledge_service() -> AssistantKnowledgeService:
    """获取辅助 Agent 知识检索服务（Milvus collection，进程内单例）"""
    return AssistantKnowledgeService(get_milvus_client())


AssistantKnowledgeServiceDep = Annotated[
    AssistantKnowledgeService, Depends(get_assistant_knowledge_service)
]