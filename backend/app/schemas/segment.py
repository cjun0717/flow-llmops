#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档片段 Schema（Pydantic，迁移自 imooc segment_schema.py）。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.dataset import Segment
from app.schemas.response import PageParams


def _ts(dt: datetime | None) -> int:
    return int(dt.timestamp()) if dt else 0


class GetSegmentsWithPageReq(PageParams):
    """获取文档片段列表请求"""
    search_word: str = Field("", description="搜索词")


class SegmentListItemData(BaseModel):
    """片段列表项"""
    id: UUID
    document_id: UUID
    dataset_id: UUID
    position: int = 0
    content: str = ""
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


class SegmentDetailData(BaseModel):
    """片段详情"""
    id: UUID
    document_id: UUID
    dataset_id: UUID
    position: int = 0
    content: str = ""
    keywords: list[str] = Field(default_factory=list)
    character_count: int = 0
    token_count: int = 0
    hit_count: int = 0
    hash: str = ""
    enabled: bool = False
    disabled_at: int = 0
    status: str = ""
    error: str = ""
    updated_at: int = 0
    created_at: int = 0


class CreateSegmentReq(BaseModel):
    """创建文档片段请求"""
    content: str = Field(..., min_length=1, description="片段内容")
    keywords: list[str] = Field(default_factory=list, max_length=10, description="关键词列表")


class UpdateSegmentReq(BaseModel):
    """更新文档片段请求"""
    content: str = Field(..., min_length=1, description="片段内容")
    keywords: list[str] = Field(default_factory=list, max_length=10, description="关键词列表")


class UpdateSegmentEnabledReq(BaseModel):
    """更新片段启用状态请求"""
    enabled: bool
