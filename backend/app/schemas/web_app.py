#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WebApp Schema（迁移自 imooc web_app_schema.py）。"""
from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class WebAppChatReq(BaseModel):
    """WebApp 对话请求结构体"""
    conversation_id: str = Field(default="", description="会话id，空则新建")
    query: str = Field(..., min_length=1, description="用户提问query")
    image_urls: list[str] = Field(default_factory=list, description="图片URL列表")

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, value: str) -> str:
        if value:
            try:
                uuid.UUID(value)
            except Exception:
                raise ValueError("会话id格式必须为uuid")
        return value

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            return []
        if len(value) > 5:
            raise ValueError("上传的图片数量不能超过5，请核实后重试")
        for image_url in value:
            result = urlparse(image_url)
            if not all([result.scheme, result.netloc]):
                raise ValueError("上传的图片URL地址格式错误，请核实后重试")
        return value


class WebAppConfigData(BaseModel):
    """WebApp 运行时配置（前端需要的子集）"""
    opening_statement: str = ""
    opening_questions: list[str] = Field(default_factory=list)
    suggested_after_answer: dict[str, Any] = Field(default_factory=dict)
    features: list[str] = Field(default_factory=list)
    text_to_speech: dict[str, Any] = Field(default_factory=dict)
    speech_to_text: dict[str, Any] = Field(default_factory=dict)


class WebAppInfoData(BaseModel):
    """根据 token 获取 WebApp 基础信息"""
    id: UUID
    icon: str
    name: str
    description: str
    app_config: WebAppConfigData


class WebAppConversationItem(BaseModel):
    """WebApp 会话列表项"""
    id: UUID
    name: str
    summary: str
    created_at: int
