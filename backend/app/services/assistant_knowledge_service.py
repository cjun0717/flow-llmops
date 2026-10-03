#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""辅助 Agent 知识检索（Milvus collection，替代 imooc 本地 FAISS）。

课程/项目文档种子在 assistant_docs.json；首次使用且 collection 为空时写入 Milvus。
检索走账号默认向量模型 + COSINE，不再使用环境变量 embedding。
"""
from __future__ import annotations

import json
import logging
import os
from uuid import UUID

from langchain_core.documents import Document as LCDocument
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient

from app.config import settings
from app.core.agent.entities.agent_entity import DATASET_RETRIEVAL_TOOL_NAME
from app.exceptions import FailException
from app.lib.helper import combine_documents
from app.models.user_model import UserModelType
from app.services.embeddings_service import EmbeddingsService
from app.services.vector_database_service import LEGACY_COLLECTION_DIM

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

    def __init__(self, client: MilvusClient) -> None:
        self.client = client
        self._ready_dims: set[int] = set()

    def collection_name_for(self, dimension: int) -> str:
        base = settings.MILVUS_ASSISTANT_COLLECTION_NAME or ASSISTANT_COLLECTION_NAME
        if dimension == LEGACY_COLLECTION_DIM:
            return base
        return f"{base}_{dimension}"

    def _resolve_embedding(self, account_id: UUID | None) -> tuple[EmbeddingsService, int]:
        from app.db import SyncSessionLocal
        from app.deps import get_sync_redis
        from app.services.user_model_service import UserModelService

        if account_id is None:
            raise FailException("请先在模型管理中添加向量模型")
        with SyncSessionLocal() as db:
            record = UserModelService.get_default_sync(account_id, UserModelType.EMBEDDING, db)
        if record is None or not record.dimension:
            raise FailException("请先在模型管理中添加向量模型")
        embeddings = EmbeddingsService.from_user_model(record, get_sync_redis())
        return embeddings, int(record.dimension)

    def _ensure_ready(self, dimension: int, embeddings: EmbeddingsService) -> None:
        if dimension in self._ready_dims:
            return
        self._ensure_collection(dimension)
        self._seed_if_empty(dimension, embeddings)
        self._ready_dims.add(dimension)

    def _ensure_collection(self, dimension: int) -> None:
        name = self.collection_name_for(dimension)
        if self.client.has_collection(name):
            self.client.load_collection(name)
            return

        pk = FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=36)
        vector = FieldSchema(
            name="vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=dimension,
        )
        text = FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535)
        source = FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512)
        schema = CollectionSchema(
            fields=[pk, vector, text, source],
            description="辅助Agent课程知识向量",
            enable_dynamic_field=False,
        )
        self.client.create_collection(collection_name=name, schema=schema)
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="FLAT",
            metric_type="COSINE",
            params={},
        )
        self.client.create_index(
            collection_name=name,
            index_params=index_params,
        )
        self.client.load_collection(name)

    def _row_count(self, dimension: int) -> int:
        name = self.collection_name_for(dimension)
        try:
            stats = self.client.get_collection_stats(name)
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

    def _seed_if_empty(self, dimension: int, embeddings_service: EmbeddingsService) -> None:
        if self._row_count(dimension) > 0:
            return
        docs = self._load_seed_docs()
        if not docs:
            return

        name = self.collection_name_for(dimension)
        logger.info("辅助Agent知识库为空，开始从种子导入 %s 条", len(docs))
        embeddings = embeddings_service.embeddings
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
            self.client.upsert(collection_name=name, data=payload)
        logger.info("辅助Agent知识库导入完成")

    def search(
        self,
        query: str,
        top_k: int = 5,
        account_id: UUID | None = None,
    ) -> list[LCDocument]:
        """语义检索辅助 Agent 知识"""
        embeddings_service, dimension = self._resolve_embedding(account_id)
        self._ensure_ready(dimension, embeddings_service)
        name = self.collection_name_for(dimension)
        query_vector = embeddings_service.embeddings.embed_query(query)
        results = self.client.search(
            collection_name=name,
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

    def convert_to_tool(self, account_id: UUID | None = None) -> BaseTool:
        """转换成 LangChain 知识检索工具（工具名仍为 dataset_retrieval，对齐 Agent 约定）"""

        class DatasetRetrievalInput(BaseModel):
            """知识库检索工具输入结构"""
            query: str = Field(description="知识库检索query语句，类型为字符串")

        @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)
        def dataset_retrieval(query: str) -> str:
            """如果需要检索扩展的知识库内容，当你觉得用户的提问超过你的知识范围时，可以尝试调用该工具，输入为搜索query语句，返回数据为检索内容字符串"""
            documents = self.search(query, top_k=5, account_id=account_id)
            if not documents:
                return "知识库内没有检索到对应内容"
            return combine_documents(documents)

        return dataset_retrieval
