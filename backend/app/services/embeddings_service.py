#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文本嵌入模型服务（OpenAI + Redis 缓存）。

迁移自 imooc internal/service/embeddings_service.py。
"""
from __future__ import annotations

import tiktoken
from langchain_classic.embeddings import CacheBackedEmbeddings
from langchain_community.storage import RedisStore
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from redis import Redis

from app.config import settings


class EmbeddingsService:
    """文本嵌入模型服务"""

    def __init__(self, redis: Redis) -> None:
        self._store = RedisStore(client=redis)
        self._embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            api_key=settings.OPENAI_EMBEDDING_API_KEY,
            base_url=settings.OPENAI_EMBEDDING_BASE_URL,
        )
        self._cache_backed_embeddings = CacheBackedEmbeddings.from_bytes_store(
            self._embeddings,
            self._store,
            namespace="embeddings",
        )

    @classmethod
    def calculate_token_count(cls, query: str) -> int:
        """计算传入文本的 token 数"""
        encoding = tiktoken.encoding_for_model("gpt-3.5")
        return len(encoding.encode(query))

    @property
    def store(self) -> RedisStore:
        return self._store

    @property
    def embeddings(self) -> Embeddings:
        """裸 embedding（segment 更新向量时用，绕过缓存）"""
        return self._embeddings

    @property
    def cache_backed_embeddings(self) -> CacheBackedEmbeddings:
        """缓存版 embedding（写入向量库时用）"""
        return self._cache_backed_embeddings
