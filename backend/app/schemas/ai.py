#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI 辅助相关 Pydantic schema（迁移自 imooc ai_schema.py）。"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class GenerateSuggestedQuestionsReq(BaseModel):
    """生成建议问题列表请求结构体"""
    message_id: UUID = Field(..., description="消息id")


class OptimizePromptReq(BaseModel):
    """优化预设 prompt 请求结构体"""
    prompt: str = Field(..., min_length=1, max_length=2000, description="预设prompt")
