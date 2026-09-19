#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""向量数据库服务（Milvus adapter，替代 imooc 的 Weaviate）。

使用 pymilvus.MilvusClient 直接封装，提供 upsert/search/delete 契约。
collection schema：pk=node_id(VARCHAR 36) + vector(FLOAT_VECTOR 3072) + 标量字段。
"""
from __future__ import annotations

from typing import Any

from langchain_core.documents import Document as LCDocument
from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient

from app.config import settings
from app.services.embeddings_service import EmbeddingsService

# 向量数据库的默认集合名字
COLLECTION_NAME = "Dataset"


class VectorDatabaseService:
    """Milvus 向量数据库服务"""

    def __init__(self, client: MilvusClient, embeddings_service: EmbeddingsService) -> None:
        self.client = client
        self.embeddings_service = embeddings_service
        self._ensure_collection()

    @property
    def collection_name(self) -> str:
        return settings.MILVUS_COLLECTION_NAME or COLLECTION_NAME

    def _ensure_collection(self) -> None:
        """确保 collection 存在，不存在则按 schema 创建"""
        if self.client.has_collection(self.collection_name):
            return

        pk = FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=36)
        vector = FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIMENSION)
        text = FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535)
        account_id = FieldSchema(name="account_id", dtype=DataType.VARCHAR, max_length=36)
        dataset_id = FieldSchema(name="dataset_id", dtype=DataType.VARCHAR, max_length=36)
        document_id = FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36)
        segment_id = FieldSchema(name="segment_id", dtype=DataType.VARCHAR, max_length=36)
        document_enabled = FieldSchema(name="document_enabled", dtype=DataType.BOOL)
        segment_enabled = FieldSchema(name="segment_enabled", dtype=DataType.BOOL)

        schema = CollectionSchema(
            fields=[pk, vector, text, account_id, dataset_id, document_id, segment_id, document_enabled, segment_enabled],
            description="知识库片段向量",
            enable_dynamic_field=False,
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
        )
        # 创建向量索引
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="FLAT",
            metric_type="COSINE",
            params={},
        )
        self.client.create_index(
            collection_name=self.collection_name,
            index_params=index_params,
        )
        # 加载 collection 到内存以便搜索/查询
        self.client.load_collection(self.collection_name)

    def add_documents(self, documents: list[LCDocument], ids: list[str]) -> list[str]:
        """批量写入向量（upsert），返回 ids"""
        texts = [doc.page_content for doc in documents]
        vectors = self.embeddings_service.cache_backed_embeddings.embed_documents(texts)
        data = []
        for doc, node_id, vec in zip(documents, ids, vectors):
            meta = doc.metadata or {}
            data.append({
                "pk": node_id,
                "vector": vec,
                "text": doc.page_content,
                "account_id": str(meta.get("account_id", "")),
                "dataset_id": str(meta.get("dataset_id", "")),
                "document_id": str(meta.get("document_id", "")),
                "segment_id": str(meta.get("segment_id", "")),
                "document_enabled": bool(meta.get("document_enabled", False)),
                "segment_enabled": bool(meta.get("segment_enabled", False)),
            })
        self.client.upsert(collection_name=self.collection_name, data=data)
        return ids

    def update_by_id(self, node_id: str, properties: dict[str, Any], vector: list[float] | None = None) -> None:
        """按 pk 更新标量字段（及可选向量）"""
        data: dict[str, Any] = {"pk": node_id}
        data.update(properties)
        if vector is not None:
            data["vector"] = vector
        self.client.upsert(collection_name=self.collection_name, data=[data])

    def delete_by_id(self, node_id: str) -> None:
        """按 pk 删除"""
        self.client.delete(collection_name=self.collection_name, filter=f'pk == "{node_id}"')

    def delete_by_document_id(self, document_id: str) -> None:
        """按 document_id 删除该文档下所有向量"""
        self.client.delete(
            collection_name=self.collection_name,
            filter=f'document_id == "{document_id}"',
        )

    def delete_by_dataset_id(self, dataset_id: str) -> None:
        """按 dataset_id 删除该知识库下所有向量"""
        self.client.delete(
            collection_name=self.collection_name,
            filter=f'dataset_id == "{dataset_id}"',
        )

    def search(
        self,
        query: str,
        top_k: int,
        dataset_ids: list[str],
        score_threshold: float = 0.0,
    ) -> list[LCDocument]:
        """向量检索（5b 使用，5a 占位实现）"""
        query_vector = self.embeddings_service.embeddings.embed_query(query)
        dataset_filter = ", ".join([f'"{did}"' for did in dataset_ids])
        expr = (
            f'dataset_id in [{dataset_filter}] '
            f'and document_enabled == true and segment_enabled == true'
        )
        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            filter=expr,
            limit=top_k,
            output_fields=["text", "account_id", "dataset_id", "document_id", "segment_id", "document_enabled", "segment_enabled"],
        )
        lcdocs: list[LCDocument] = []
        if not results:
            return lcdocs
        hits = results[0]
        for hit in hits:
            entity = hit.get("entity", {}) if isinstance(hit, dict) else {}
            score = hit.get("distance", 0.0) if isinstance(hit, dict) else 0.0
            if score_threshold and score < score_threshold:
                continue
            lcdocs.append(LCDocument(
                page_content=entity.get("text", ""),
                metadata={
                    "score": score,
                    "account_id": entity.get("account_id", ""),
                    "dataset_id": entity.get("dataset_id", ""),
                    "document_id": entity.get("document_id", ""),
                    "segment_id": entity.get("segment_id", ""),
                    "node_id": hit.get("id", "") if isinstance(hit, dict) else "",
                },
            ))
        return lcdocs
