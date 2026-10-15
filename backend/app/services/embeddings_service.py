#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文本嵌入模型服务（OpenAI 兼容 + Redis 缓存）。

凭证与模型名来自用户在前端添加的向量模型，不再读取环境变量。
"""
from __future__ import annotations

import hashlib
import json

import tiktoken
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from redis import Redis


class CacheBackedEmbeddings(Embeddings):
    """文本向量 Redis 缓存包装。

    替代已停止维护的 langchain-community/classic 中的 CacheBackedEmbeddings：
    embed_documents 按 namespace+文本哈希逐条缓存（JSON 存取向量），
    embed_query 直接透传不缓存，语义与官方实现一致。
    """

    def __init__(self, underlying: Embeddings, redis: Redis, namespace: str = "") -> None:
        self._underlying = underlying
        self._redis = redis
        self._namespace = namespace

    def _key(self, text: str) -> str:
        digest = hashlib.sha1(f"{self._namespace}{text}".encode("utf-8")).hexdigest()
        return f"{self._namespace}:{digest}" if self._namespace else digest

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """带缓存的文档向量化：命中缓存的直接返回，未命中的批量计算后写入缓存。"""
        keys = [self._key(text) for text in texts]
        cached = self._redis.mget(keys)
        results: list[list[float] | None] = [
            json.loads(value) if value is not None else None for value in cached
        ]
        missed_indexes = [i for i, vector in enumerate(results) if vector is None]
        if missed_indexes:
            missed_texts = [texts[i] for i in missed_indexes]
            missed_vectors = self._underlying.embed_documents(missed_texts)
            pipe = self._redis.pipeline(transaction=False)
            for index, vector in zip(missed_indexes, missed_vectors):
                results[index] = vector
                pipe.set(keys[index], json.dumps(vector))
            pipe.execute()
        return results  # type: ignore[return-value]

    def embed_query(self, text: str) -> list[float]:
        """查询向量直接透传（与官方 CacheBackedEmbeddings 一致，不缓存）。"""
        return self._underlying.embed_query(text)


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
            inst._cache_backed_embeddings = inst._embeddings
            return inst
        inst._cache_backed_embeddings = CacheBackedEmbeddings(
            inst._embeddings,
            redis,
            namespace=f"embeddings:{record.id}",
        )
        return inst

    @classmethod
    def calculate_token_count(cls, query: str) -> int:
        """计算传入文本的 token 数"""
        encoding = tiktoken.encoding_for_model("gpt-3.5")
        return len(encoding.encode(query))

    @property
    def embeddings(self) -> Embeddings:
        """裸 embedding（segment 更新向量时用，绕过缓存）"""
        return self._embeddings

    @property
    def cache_backed_embeddings(self) -> Embeddings:
        """缓存版 embedding（写入向量库时用）"""
        return self._cache_backed_embeddings