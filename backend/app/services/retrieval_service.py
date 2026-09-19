#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检索服务（async，迁移自 imooc retrieval_service.py）。

支持 semantic / full_text / hybrid 三策略，hybrid 自实现合并排序
（不引入 LangChain EnsembleRetriever）。同步向量检索用 run_in_threadpool 包装。
"""
from __future__ import annotations

from collections import Counter
from uuid import UUID

from langchain_core.documents import Document as LCDocument
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.entities.dataset_entity import RetrievalSource, RetrievalStrategy
from app.exceptions import NotFoundException
from app.models.dataset import Dataset, DatasetQuery, KeywordTable, Segment
from app.services.jieba_service import JiebaService
from app.services.vector_database_service import VectorDatabaseService


class RetrievalService:
    """检索服务"""

    def __init__(
        self,
        jieba_service: JiebaService,
        vector_database_service: VectorDatabaseService,
    ) -> None:
        self.jieba_service = jieba_service
        self.vector_database_service = vector_database_service

    async def search_in_datasets(
        self,
        dataset_ids: list[UUID],
        query: str,
        account_id: UUID,
        db: AsyncSession,
        retrieval_strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC,
        k: int = 4,
        score: float = 0,
        retrieval_source: str = RetrievalSource.HIT_TESTING,
    ) -> list[LCDocument]:
        """根据 query + 知识库列表执行检索，返回 LangChain 文档列表（含 score）"""
        # 1.校验知识库权限并提取有效 dataset_ids
        result = await db.execute(
            select(Dataset).where(Dataset.id.in_(dataset_ids), Dataset.account_id == account_id)
        )
        datasets = result.scalars().all()
        if not datasets:
            raise NotFoundException("当前无知识库可执行检索")
        valid_dataset_ids = [str(d.id) for d in datasets]

        # 2.按策略分发检索
        if retrieval_strategy == RetrievalStrategy.SEMANTIC:
            lc_documents = await self._search_semantic(query, k, valid_dataset_ids, score)
        elif retrieval_strategy == RetrievalStrategy.FULL_TEXT:
            lc_documents = await self._search_full_text(query, k, valid_dataset_ids, db)
        else:
            lc_documents = await self._search_hybrid(query, k, valid_dataset_ids, score, db)

        # 3.写 DatasetQuery（每个命中的 dataset_id 一条）
        unique_dataset_ids = list({
            str(doc.metadata.get("dataset_id")) for doc in lc_documents if doc.metadata.get("dataset_id")
        })
        for did in unique_dataset_ids:
            db.add(DatasetQuery(
                dataset_id=UUID(did),
                query=query,
                source=retrieval_source,
                source_app_id=None,
                created_by=account_id,
            ))
        await db.commit()

        # 4.批量更新片段命中次数
        segment_ids = [doc.metadata.get("segment_id") for doc in lc_documents if doc.metadata.get("segment_id")]
        if segment_ids:
            await db.execute(
                update(Segment)
                .where(Segment.id.in_([UUID(sid) for sid in segment_ids]))
                .values(hit_count=Segment.hit_count + 1)
            )
            await db.commit()

        return lc_documents

    async def _search_semantic(
        self, query: str, k: int, dataset_ids: list[str], score: float
    ) -> list[LCDocument]:
        """向量检索（同步调用，用 threadpool 包装）"""
        return await run_in_threadpool(
            self.vector_database_service.search,
            query=query,
            top_k=k,
            dataset_ids=dataset_ids,
            score_threshold=score,
        )

    async def _search_full_text(
        self, query: str, k: int, dataset_ids: list[str], db: AsyncSession
    ) -> list[LCDocument]:
        """全文检索：jieba 分词 + KeywordTable 倒排 + 频率排序，score 恒 0"""
        # 1.提取查询关键词
        keywords = self.jieba_service.extract_keywords(query, 10)
        if not keywords:
            return []

        # 2.查指定知识库的关键词表
        result = await db.execute(
            select(KeywordTable.keyword_table).where(
                KeywordTable.dataset_id.in_([UUID(did) for did in dataset_ids])
            )
        )
        keyword_tables = [row[0] for row in result.all()]

        # 3.遍历关键词表，匹配 query 关键词，收集 segment_id
        all_ids: list[str] = []
        for keyword_table in keyword_tables:
            for keyword, segment_ids in keyword_table.items():
                if keyword in keywords:
                    all_ids.extend(segment_ids)

        if not all_ids:
            return []

        # 4.频率统计取 top_k
        id_counter = Counter(all_ids)
        top_k_ids = id_counter.most_common(k)
        if not top_k_ids:
            return []

        # 5.查 Segment
        seg_result = await db.execute(
            select(Segment).where(Segment.id.in_([UUID(sid) for sid, _ in top_k_ids]))
        )
        segment_dict = {str(seg.id): seg for seg in seg_result.scalars().all()}

        # 6.按频率排序构建 LCDocument
        lc_documents: list[LCDocument] = []
        for sid, _freq in top_k_ids:
            segment = segment_dict.get(sid)
            if segment is None:
                continue
            lc_documents.append(LCDocument(
                page_content=segment.content,
                metadata={
                    "account_id": str(segment.account_id),
                    "dataset_id": str(segment.dataset_id),
                    "document_id": str(segment.document_id),
                    "segment_id": str(segment.id),
                    "node_id": str(segment.node_id),
                    "document_enabled": True,
                    "segment_enabled": True,
                    "score": 0,
                },
            ))
        return lc_documents

    async def _search_hybrid(
        self,
        query: str,
        k: int,
        dataset_ids: list[str],
        score: float,
        db: AsyncSession,
    ) -> list[LCDocument]:
        """混合检索：semantic + full_text 合并去重 + 加权排序"""
        # 并行执行两种检索（semantic 走 threadpool，full_text 走 async）
        import asyncio

        sem_task = asyncio.create_task(self._search_semantic(query, k, dataset_ids, score))
        ft_task = asyncio.create_task(self._search_full_text(query, k, dataset_ids, db))
        sem_docs, ft_docs = await asyncio.gather(sem_task, ft_task)

        # full_text 频率归一化（用 Counter 重算，因为 _search_full_text 已截断到 k）
        ft_freq: Counter = Counter()
        for doc in ft_docs:
            ft_freq[str(doc.metadata.get("segment_id"))] += 1
        max_ft = max(ft_freq.values()) if ft_freq else 1

        # 合并去重（按 segment_id）
        merged: dict[str, dict] = {}
        for doc in sem_docs:
            sid = str(doc.metadata.get("segment_id"))
            if not sid:
                continue
            merged[sid] = {
                "doc": doc,
                "sem_score": float(doc.metadata.get("score", 0.0)),
                "ft_score": 0.0,
            }
        for doc in ft_docs:
            sid = str(doc.metadata.get("segment_id"))
            if not sid:
                continue
            freq = ft_freq.get(sid, 0)
            ft_norm = freq / max_ft if max_ft else 0.0
            if sid in merged:
                merged[sid]["ft_score"] = ft_norm
            else:
                merged[sid] = {
                    "doc": doc,
                    "sem_score": 0.0,
                    "ft_score": ft_norm,
                }

        # 加权排序：0.5 * sem_score + 0.5 * ft_score
        ranked = sorted(
            merged.values(),
            key=lambda x: 0.5 * x["sem_score"] + 0.5 * x["ft_score"],
            reverse=True,
        )[:k]

        # 组装结果，score 用加权值
        lc_documents: list[LCDocument] = []
        for item in ranked:
            doc = item["doc"]
            combined_score = 0.5 * item["sem_score"] + 0.5 * item["ft_score"]
            new_meta = dict(doc.metadata)
            new_meta["score"] = combined_score
            lc_documents.append(LCDocument(page_content=doc.page_content, metadata=new_meta))
        return lc_documents
