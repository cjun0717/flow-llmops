#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文本嵌入模型服务（OpenAI 兼容 + Redis 缓存）。

凭证与模型名来自用户在前端添加的向量模型，不再读取环境变量。
"""
from __future__ import annotations

import tiktoken
from langchain_classic.embeddings import CacheBackedEmbeddings
from langchain_community.storage import RedisStore
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from redis import Redis


class EmbeddingsService:
    """文本嵌入模型服务"""

    @classmethod
    def from_user_model(cls, record, redis: Redis | None = None) -> "EmbeddingsService":
        """按用户向量模型构造实例；redis 为空时不启用缓存（连通性探测）。"""
        inst = object.__new__(cls)
        inst._embeddings = OpenAIEmbeddings(
            model=record.model_serve_name,
            api_key=record.api_key or "EMPTY",
            base_url=record.base_url or None,
            check_embedding_ctx_length=False,
        )
        if redis is None:
            inst._store = None
            inst._cache_backed_embeddings = inst._embeddings
            return inst
        inst._store = RedisStore(client=redis)
        inst._cache_backed_embeddings = CacheBackedEmbeddings.from_bytes_store(
            inst._embeddings,
            inst._store,
            namespace=f"embeddings:{record.id}",
        )
        return inst

    @classmethod
    def calculate_token_count(cls, query: str) -> int:
        """计算传入文本的 token 数"""
        encoding = tiktoken.encoding_for_model("gpt-3.5")
        return len(encoding.encode(query))

    @property
    def store(self) -> RedisStore | None:
        return self._store

    @property
    def embeddings(self) -> Embeddings:
        """裸 embedding（segment 更新向量时用，绕过缓存）"""
        return self._embeddings

    @property
    def cache_backed_embeddings(self) -> Embeddings:
        """缓存版 embedding（写入向量库时用）"""
        return self._cache_backed_embeddings
