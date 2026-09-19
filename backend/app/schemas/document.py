#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档 Schema（Pydantic，迁移自 imooc document_schema.py）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.entities.dataset_entity import DEFAULT_PROCESS_RULE, ProcessType
from app.models.dataset import Document
from app.schemas.response import PageParams


def _ts(dt: datetime | None) -> int:
    return int(dt.timestamp()) if dt else 0


class PreProcessRule(BaseModel):
    """预处理规则项"""
    id: str = Field(..., description="规则id：remove_extra_space / remove_url_and_email")
    enabled: bool


class SegmentRule(BaseModel):
    """分段设置"""
    separators: list[str] = Field(..., min_length=1, description="分隔符列表")
    chunk_size: int = Field(..., ge=100, le=1000, description="分割块大小")
    chunk_overlap: int = Field(..., ge=0, description="块重叠大小")


class DocumentRule(BaseModel):
    """文档处理规则"""
    pre_process_rules: list[PreProcessRule]
    segment: SegmentRule


class CreateDocumentsReq(BaseModel):
    """创建文档列表请求"""
    upload_file_ids: list[UUID] = Field(..., min_length=1, max_length=10, description="上传文件id列表")
    process_type: ProcessType = Field(..., description="处理类型：automatic / custom")
    rule: dict[str, Any] | None = Field(None, description="自定义处理规则")

    @model_validator(mode="after")
    def _validate_rule(self) -> "CreateDocumentsReq":
        if self.process_type == ProcessType.AUTOMATIC:
            self.rule = DEFAULT_PROCESS_RULE["rule"]
        else:
            if not self.rule:
                raise ValueError("自定义处理模式下，rule不能为空")
            # 校验并规范化 pre_process_rules
            ppr_raw = self.rule.get("pre_process_rules")
            if not isinstance(ppr_raw, list):
                raise ValueError("pre_process_rules必须为列表")
            unique: dict[str, PreProcessRule] = {}
            for item in ppr_raw:
                if not isinstance(item, dict) or item.get("id") not in ("remove_extra_space", "remove_url_and_email"):
                    raise ValueError("预处理id格式错误")
                if not isinstance(item.get("enabled"), bool):
                    raise ValueError("预处理enabled格式错误")
                unique[item["id"]] = PreProcessRule(id=item["id"], enabled=item["enabled"])
            if len(unique) != 2:
                raise ValueError("预处理规则格式错误，请重试尝试")
            # 校验 segment
            seg = self.rule.get("segment")
            if not isinstance(seg, dict):
                raise ValueError("分段设置不能为空且为字典")
            seg_rule = SegmentRule(**seg)
            self.rule = {
                "pre_process_rules": [r.model_dump() for r in unique.values()],
                "segment": seg_rule.model_dump(),
            }
        return self


class CreateDocumentsData(BaseModel):
    """创建文档列表响应"""
    documents: list[dict]
    batch: str


class DocumentListItemData(BaseModel):
    """文档列表项"""
    id: UUID
    name: str
    character_count: int = 0
    hit_count: int = 0
    position: int = 0
    enabled: bool = False
    disabled_at: int = 0
    status: str = ""
    error: str = ""
    updated_at: int = 0
    created_at: int = 0


class DocumentDetailData(BaseModel):
    """文档详情"""
    id: UUID
    dataset_id: UUID
    name: str
    segment_count: int = 0
    character_count: int = 0
    hit_count: int = 0
    position: int = 0
    enabled: bool = False
    disabled_at: int = 0
    status: str = ""
    error: str = ""
    updated_at: int = 0
    created_at: int = 0


class UpdateDocumentNameReq(BaseModel):
    """更新文档名称请求"""
    name: str = Field(..., min_length=1, max_length=100, description="文档名称")


class GetDocumentsWithPageReq(PageParams):
    """获取文档分页列表请求"""
    search_word: str = Field("", description="搜索词")


class UpdateDocumentEnabledReq(BaseModel):
    """更新文档启用状态请求"""
    enabled: bool
