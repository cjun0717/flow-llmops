#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""会话模块 Schema（迁移自 imooc conversation_schema.py / app_schema.py 的会话部分）。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.lib.helper import datetime_to_timestamp
from app.models.conversation import Message
from app.schemas.response import PageParams


class GetConversationMessagesWithPageReq(PageParams):
    """获取指定会话消息列表分页数据请求结构"""
    created_at: int = Field(default=0, ge=0, description="created_at游标，0代表不限制")


class MessageAgentThoughtItem(BaseModel):
    """智能体推理步骤响应项"""
    id: UUID
    position: int
    event: str
    thought: str
    observation: str
    tool: str
    tool_input: dict
    latency: float
    created_at: int


class MessageItem(BaseModel):
    """会话消息响应项"""
    id: UUID
    conversation_id: UUID
    query: str
    image_urls: list[str] = Field(default_factory=list)
    answer: str
    total_token_count: int
    latency: float
    agent_thoughts: list[MessageAgentThoughtItem] = Field(default_factory=list)
    created_at: int

    @classmethod
    def from_model(cls, data: Message) -> "MessageItem":
        return cls(
            id=data.id,
            conversation_id=data.conversation_id,
            query=data.query,
            image_urls=data.image_urls or [],
            answer=data.answer,
            total_token_count=data.total_token_count,
            latency=data.latency,
            agent_thoughts=[
                MessageAgentThoughtItem(
                    id=agent_thought.id,
                    position=agent_thought.position,
                    event=agent_thought.event,
                    thought=agent_thought.thought,
                    observation=agent_thought.observation,
                    tool=agent_thought.tool,
                    tool_input=agent_thought.tool_input or {},
                    latency=agent_thought.latency,
                    created_at=datetime_to_timestamp(agent_thought.created_at),
                )
                for agent_thought in (data.agent_thoughts or [])
            ],
            created_at=datetime_to_timestamp(data.created_at),
        )


class UpdateConversationNameReq(BaseModel):
    """更新会话名字请求结构体"""
    name: str = Field(..., min_length=1, max_length=100, description="会话名字")


class UpdateConversationIsPinnedReq(BaseModel):
    """更新会话置顶选项请求结构体"""
    is_pinned: bool = Field(default=False, description="是否置顶")


class UpdateDebugConversationSummaryReq(BaseModel):
    """更新应用调试会话长期记忆请求体"""
    summary: str = Field(default="", description="长期记忆摘要")


class DebugChatReq(BaseModel):
    """应用调试会话请求结构体"""
    query: str = Field(..., min_length=1, description="用户提问query")
    image_urls: list[str] = Field(default_factory=list, max_length=5, description="图片URL列表")


class GetDebugConversationMessagesWithPageReq(PageParams):
    """获取调试会话消息列表分页请求结构体"""
    created_at: int = Field(default=0, ge=0, description="created_at游标，0代表不限制")


class GetDebugConversationSummaryData(BaseModel):
    """调试会话长期记忆响应数据"""
    summary: str
