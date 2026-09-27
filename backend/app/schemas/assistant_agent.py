#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""辅助 Agent Schema（迁移自 imooc assistant_agent_schema.py）。"""
from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from app.schemas.response import PageParams


class AssistantAgentChatReq(BaseModel):
    """辅助 Agent 会话请求结构体"""
    query: str = Field(..., min_length=1, description="用户提问query")
    image_urls: list[str] = Field(default_factory=list, description="图片URL列表")

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


class GetAssistantAgentMessagesWithPageReq(PageParams):
    """获取辅助智能体消息列表分页请求"""
    created_at: int = Field(default=0, ge=0, description="created_at游标，0代表不限制")
