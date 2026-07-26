#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from typing import Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, Boolean, Numeric, Float, text, PrimaryKeyConstraint, Index, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from .base_model import BaseModel



class Conversation(BaseModel):
    """交流会话模型"""
    __tablename__ = "conversation"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_conversation_id"),
        Index("conversation_app_id_idx", "app_id"),
        Index("conversation_app_created_by_idx", "created_by"),
        {'comment': '交流会话模型'}
    )

    app_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联应用id"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="会话名称"
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="会话摘要/长期记忆"
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="是否置顶"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="是否删除"
    )
    invoke_from: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="调用来源"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        comment="会话创建者，会随着invoke_from的差异记录不同的信息，其中web_app和debugger会记录账号id、service_api会记录终端用户id"
    )





class Message(BaseModel):
    """交流消息模型"""
    __tablename__ = "message"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_id"),
        Index("message_conversation_id_idx", "conversation_id"),
        Index("message_created_by_idx", "created_by"),
        {'comment': '交流消息模型'}
    )

    app_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联应用id"
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联会话id"
    )
    invoke_from: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="调用来源，涵盖service_api、web_app、debugger等"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="消息的创建来源，有可能是LLMOps的用户，也有可能是开放API的终端用户"
    )

    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="用户提问的原始query"
    )
    image_urls: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="用户提问的图片URL列表信息"
    )
    message: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="产生answer的消息列表"
    )
    message_token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="消息列表的token总数"
    )
    message_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 7),
        nullable=False,
        server_default=text("0.0"),
        comment="消息的单价"
    )
    message_price_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0.0"),
        comment="消息的价格单位"
    )

    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="Agent生成的消息答案"
    )
    answer_token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="消息答案的token数"
    )
    answer_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 7),
        nullable=False,
        server_default=text("0.0"),
        comment="token的单位价格"
    )
    answer_price_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0.0"),
        comment="token的价格单位"
    )

    latency: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0.0"),
        comment="消息的总耗时"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="软删除标记"
    )
    status: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="消息的状态，涵盖正常、错误、停止"
    )
    error: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="发生错误时记录的信息"
    )
    total_token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="消耗的总token数，计算步骤的消耗"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 7),
        nullable=False,
        server_default=text("0.0"),
        comment="消耗的总价格，计算步骤的总消耗"
    )

    agent_thoughts = relationship(
        "MessageAgentThought",
        backref="msg",
        lazy="selectin",
        passive_deletes="all",
        uselist=True,
        foreign_keys=[id],
        primaryjoin="MessageAgentThought.message_id == Message.id",
    )



class MessageAgentThought(BaseModel):
    """智能体消息推理模型，用于记录Agent生成最终消息答案时"""
    __tablename__ = "message_agent_thought"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_message_agent_thought_id"),
        Index("message_agent_thought_app_id_idx", "app_id"),
        Index("message_agent_thought_conversation_id_idx", "conversation_id"),
        Index("message_agent_thought_message_id_idx", "message_id"),
        {'comment': '智能体消息推理模型'}
    )

    app_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的应用id"
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的会话id"
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的消息id"
    )
    invoke_from: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="调用来源，涵盖service_api、web_app、debugger等"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="消息的创建来源，有可能是LLMOps的用户，也有可能是开放API的终端用户"
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="推理观察的位置"
    )

    event: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="事件名称"
    )
    thought: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="推理内容(存储LLM生成的内容)"
    )
    observation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="观察内容(存储知识库、工具等非LLM生成的内容，用于让LLM观察)"
    )

    tool: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="调用工具名称"
    )
    tool_input: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="LLM调用工具的输入，如果没有则为空字典"
    )

    message: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="该步骤调用LLM使用的提示消息"
    )
    message_token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="消息花费的token数"
    )
    message_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 7),
        nullable=False,
        server_default=text("0.0"),
        comment="单价，所有LLM的计算方式统一为CNY"
    )
    message_price_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0"),
        comment="价格单位，值为1000代表1000token对应的单价"
    )

    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="LLM生成的答案内容，值和thought保持一致"
    )
    answer_token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="LLM生成答案消耗token数"
    )
    answer_unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 7),
        nullable=False,
        server_default=text("0.0"),
        comment="单价，所有LLM的计算方式统一为CNY"
    )
    answer_price_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        server_default=text("0.0"),
        comment="价格单位，值为1000代表1000token对应的单价"
    )

    total_token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="总消耗token"
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 7),
        nullable=False,
        server_default=text("0.0"),
        comment="总消耗"
    )
    latency: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0.0"),
        comment="推理观察步骤耗时"
    )
