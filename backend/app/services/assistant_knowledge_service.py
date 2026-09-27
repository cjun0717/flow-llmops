#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""辅助 Agent 知识检索（Milvus collection，替代 imooc 本地 FAISS）。

课程/项目文档种子在 assistant_docs.json；首次使用且 collection 为空时写入 Milvus。
检索走与知识库相同的 embedding + COSINE，不再依赖 faiss-cpu。
"""
from __future__ import annotations

import json
import logging
import os

from langchain_core.documents import Document as LCDocument
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient

from app.config import settings
from app.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME
from app.lib.helper import combine_documents
from app.services.embeddings_service import EmbeddingsService

logger = logging.getLogger(__name__)

ASSISTANT_COLLECTION_NAME = "AssistantAgent"
_SEED_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "core",
    "vector_store",
    "assistant_docs.json",
)
_SEED_BATCH = 32


class AssistantKnowledgeService:
    """辅助 Agent 专用向量检索（Milvus）"""

    def __init__(self, client: MilvusClient, embeddings_service: EmbeddingsService) -> None:
        self.client = client
        self.embeddings_service = embeddings_service
        self._ready = False

    @property
    def collection_name(self) -> str:
        return settings.MILVUS_ASSISTANT_COLLECTION_NAME or ASSISTANT_COLLECTION_NAME

    def _ensure_ready(self) -> None:
        """确保 collection 存在；为空则从 JSON 种子导入"""
        if self._ready:
            return
        self._ensure_collection()
        self._seed_if_empty()
        self._ready = True

    def _ensure_collection(self) -> None:
        if self.client.has_collection(self.collection_name):
            self.client.load_collection(self.collection_name)
            return

        pk = FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=36)
        vector = FieldSchema(
            name="vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=settings.EMBEDDING_DIMENSION,
        )
        text = FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535)
        source = FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512)
        schema = CollectionSchema(
            fields=[pk, vector, text, source],
            description="辅助Agent课程知识向量",
            enable_dynamic_field=False,
        )
        self.client.create_collection(collection_name=self.collection_name, schema=schema)
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
        self.client.load_collection(self.collection_name)

    def _row_count(self) -> int:
        try:
            stats = self.client.get_collection_stats(self.collection_name)
            if isinstance(stats, dict):
                return int(stats.get("row_count", 0) or 0)
        except Exception:
            logger.exception("读取辅助Agent collection 行数失败")
        return 0

    def _load_seed_docs(self) -> list[dict]:
        if not os.path.exists(_SEED_PATH):
            logger.warning("辅助Agent种子文件不存在: %s", _SEED_PATH)
            return []
        with open(_SEED_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return [item for item in data if item.get("id") and item.get("text")]

    def _seed_if_empty(self) -> None:
        if self._row_count() > 0:
            return
        docs = self._load_seed_docs()
        if not docs:
            return

        logger.info("辅助Agent知识库为空，开始从种子导入 %s 条", len(docs))
        embeddings = self.embeddings_service.embeddings
        for start in range(0, len(docs), _SEED_BATCH):
            batch = docs[start:start + _SEED_BATCH]
            texts = [item["text"] for item in batch]
            vectors = embeddings.embed_documents(texts)
            payload = [
                {
                    "pk": item["id"][:36],
                    "vector": vec,
                    "text": item["text"][:65535],
                    "source": str(item.get("source") or "")[:512],
                }
                for item, vec in zip(batch, vectors)
            ]
            self.client.upsert(collection_name=self.collection_name, data=payload)
        logger.info("辅助Agent知识库导入完成")

    def search(self, query: str, top_k: int = 5) -> list[LCDocument]:
        """语义检索辅助 Agent 知识"""
        self._ensure_ready()
        query_vector = self.embeddings_service.embeddings.embed_query(query)
        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            limit=top_k,
            output_fields=["text", "source"],
        )
        lcdocs: list[LCDocument] = []
        if not results:
            return lcdocs
        for hit in results[0]:
            entity = hit.get("entity", {}) if isinstance(hit, dict) else {}
            score = hit.get("distance", 0.0) if isinstance(hit, dict) else 0.0
            lcdocs.append(LCDocument(
                page_content=entity.get("text", ""),
                metadata={
                    "score": score,
                    "source": entity.get("source", ""),
                    "node_id": hit.get("id", "") if isinstance(hit, dict) else "",
                },
            ))
        return lcdocs

    def convert_to_tool(self) -> BaseTool:
        """转换成 LangChain 知识检索工具（工具名仍为 dataset_retrieval，对齐 Agent 约定）"""

        class DatasetRetrievalInput(BaseModel):
            """知识库检索工具输入结构"""
            query: str = Field(description="知识库检索query语句，类型为字符串")

        @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)
        def dataset_retrieval(query: str) -> str:
            """如果需要检索扩展的知识库内容，当你觉得用户的提问超过你的知识范围时，可以尝试调用该工具，输入为搜索query语句，返回数据为检索内容字符串"""
            documents = self.search(query, top_k=5)
            if not documents:
                return "知识库内没有检索到对应内容"
            return combine_documents(documents)

        return dataset_retrieval
