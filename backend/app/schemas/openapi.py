#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""开放 API 相关 Pydantic schema（迁移自 imooc openapi_schema.py）。"""
from __future__ import annotations

import uuid
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class OpenAPIChatReq(BaseModel):
    """开放 API 聊天接口请求结构体"""
    app_id: UUID = Field(..., description="应用id")
    end_user_id: str = Field(default="", description="终端用户id")
    conversation_id: str = Field(default="", description="会话id")
    query: str = Field(..., description="用户提问query")
    image_urls: list[str] = Field(default_factory=list, description="图片URL列表")
    stream: bool = Field(default=True, description="是否流式输出")

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, value: str) -> str:
        """校验会话id：传递了则必须为 UUID，且终端用户id不能为空"""
        if value:
            try:
                uuid.UUID(value)
            except Exception:
                raise ValueError("会话id格式必须为UUID")
        return value

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, value: list[str]) -> list[str]:
        """校验图片URL列表：最多5条，且每条必须是合法URL"""
        if not isinstance(value, list):
            return []
        if len(value) > 5:
            raise ValueError("上传的图片数量不能超过5，请核实后重试")
        for image_url in value:
            result = urlparse(image_url)
            if not all([result.scheme, result.netloc]):
                raise ValueError("上传的图片URL地址格式错误，请核实后重试")
        return value


class OpenAPIChatBlockData(BaseModel):
    """开放 API 聊天块（非流式）响应数据"""
    id: str
    end_user_id: str
    conversation_id: str
    query: str
    image_urls: list[str] = Field(default_factory=list)
    answer: str
    total_token_count: int = 0
    latency: float = 0
    agent_thoughts: list[dict] = Field(default_factory=list)
