#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库关键词表服务（Postgres JSONB 倒排索引）。

迁移自 imooc keyword_table_service.py，使用同步 SQLAlchemy Session
（在 Celery 任务和 segment_service 的同步上下文中使用）。
"""
from __future__ import annotations

from uuid import UUID

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.entities.cache_entity import (
    LOCK_EXPIRE_TIME,
    LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE,
)
from app.models.dataset import KeywordTable, Segment


class KeywordTableService:
    """知识库关键词表服务"""

    def __init__(self, redis_client: Redis) -> None:
        self.redis_client = redis_client

    def get_keyword_table_from_dataset_id(
        self, dataset_id: UUID, db: Session
    ) -> KeywordTable:
        """根据知识库 id 获取关键词表，不存在则创建"""
        keyword_table = db.execute(
            select(KeywordTable).where(KeywordTable.dataset_id == dataset_id)
        ).scalar_one_or_none()
        if keyword_table is None:
            keyword_table = KeywordTable(dataset_id=dataset_id, keyword_table={})
            db.add(keyword_table)
            db.commit()
            db.refresh(keyword_table)
        return keyword_table

    def delete_keyword_table_from_ids(
        self, dataset_id: UUID, segment_ids: list[UUID], db: Session
    ) -> None:
        """根据知识库 id + 片段 id 列表删除关键词表中对应数据"""
        cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(dataset_id=dataset_id)
        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id, db)
            keyword_table = keyword_table_record.keyword_table.copy()

            segment_ids_to_delete = {str(sid) for sid in segment_ids}
            keywords_to_delete = set()

            for keyword, ids in keyword_table.items():
                ids_set = set(ids)
                if segment_ids_to_delete.intersection(ids_set):
                    keyword_table[keyword] = list(ids_set.difference(segment_ids_to_delete))
                    if not keyword_table[keyword]:
                        keywords_to_delete.add(keyword)

            for keyword in keywords_to_delete:
                del keyword_table[keyword]

            keyword_table_record.keyword_table = keyword_table
            db.commit()

    def add_keyword_table_from_ids(
        self, dataset_id: UUID, segment_ids: list[UUID], db: Session
    ) -> None:
        """根据知识库 id + 片段 id 列表，在关键词表中添加关键词"""
        cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(dataset_id=dataset_id)
        with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
            keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id, db)
            keyword_table = {
                field: set(value) for field, value in keyword_table_record.keyword_table.items()
            }

            segments = db.execute(
                select(Segment.id, Segment.keywords).where(Segment.id.in_(segment_ids))
            ).all()

            for seg_id, keywords in segments:
                for keyword in keywords:
                    if keyword not in keyword_table:
                        keyword_table[keyword] = set()
                    keyword_table[keyword].add(str(seg_id))

            keyword_table_record.keyword_table = {
                field: list(value) for field, value in keyword_table.items()
            }
            db.commit()
