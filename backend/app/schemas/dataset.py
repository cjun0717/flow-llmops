#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库 Schema（Pydantic，迁移自 imooc dataset_schema.py）。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.entities.dataset_entity import RetrievalStrategy
from app.models.dataset import Dataset, DatasetQuery
from app.schemas.response import PageParams


def _ts(dt: datetime | None) -> int:
    return int(dt.timestamp()) if dt else 0


class CreateDatasetReq(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    icon: str = Field(..., min_length=1, description="知识库图标URL")
    description: str = Field("", max_length=2000, description="知识库描述")


class UpdateDatasetReq(BaseModel):
    """更新知识库请求"""
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    icon: str = Field(..., min_length=1, description="知识库图标URL")
    description: str = Field("", max_length=2000, description="知识库描述")


class GetDatasetsWithPageReq(PageParams):
    """获取知识库分页列表请求"""
    search_word: str = Field("", description="搜索词")


class DatasetListItemData(BaseModel):
    """知识库列表项"""
    id: UUID
    name: str
    icon: str
    description: str
    document_count: int = 0
    related_app_count: int = 0
    character_count: int = 0
    updated_at: int = 0
    created_at: int = 0


class DatasetDetailData(BaseModel):
    """知识库详情"""
    id: UUID
    name: str
    icon: str
    description: str
    document_count: int = 0
    hit_count: int = 0
    related_app_count: int = 0
    character_count: int = 0
    updated_at: int = 0
    created_at: int = 0


class HitReq(BaseModel):
    """知识库召回测试请求"""
    query: str = Field(..., min_length=1, max_length=200, description="查询语句")
    retrieval_strategy: RetrievalStrategy = Field(..., description="检索策略")
    k: int = Field(..., ge=1, le=10, description="最大召回数量")
    score: float = Field(0, ge=0, le=0.99, description="最小匹配度")


class HitDocumentData(BaseModel):
    """命中片段所属文档信息"""
    id: UUID
    name: str
    extension: str
    mime_type: str


class HitRespItem(BaseModel):
    """召回测试单条结果"""
    id: UUID
    document: HitDocumentData
    dataset_id: UUID
    score: float
    position: int
    content: str
    keywords: list[str] = Field(default_factory=list)
    character_count: int = 0
    token_count: int = 0
    hit_count: int = 0
    enabled: bool = False
    disabled_at: int = 0
    status: str = ""
    error: str = ""
    updated_at: int = 0
    created_at: int = 0


class DatasetQueryData(BaseModel):
    """知识库最近查询记录"""
    id: UUID
    dataset_id: UUID
    query: str
    source: str
    created_at: int = 0

    @classmethod
    def from_model(cls, q: DatasetQuery) -> "DatasetQueryData":
        return cls(
            id=q.id,
            dataset_id=q.dataset_id,
            query=q.query,
            source=q.source,
            created_at=_ts(q.created_at),
        )
