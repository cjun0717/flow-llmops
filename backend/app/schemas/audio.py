#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""语音 Schema（迁移自 imooc audio_schema.py）。"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class MessageToAudioReq(BaseModel):
    """消息转流式语音请求"""
    message_id: UUID = Field(..., description="消息id")


class AudioToTextData(BaseModel):
    """语音转文本响应"""
    text: str
