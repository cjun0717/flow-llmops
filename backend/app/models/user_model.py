#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""账号自定义模型目录（OpenAI 兼容对话 / 向量）。"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, text, Index, PrimaryKeyConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import BaseModel


class UserModelType:
    CHAT = "chat"
    EMBEDDING = "embedding"


class UserModel(BaseModel):
    """用户在前端添加的 OpenAI 兼容模型"""

    __tablename__ = "user_model"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_user_model_id"),
        Index("user_model_account_id_idx", "account_id"),
        Index("user_model_account_type_idx", "account_id", "model_type"),
        {"comment": "账号自定义模型目录"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, comment="归属账号")
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="显示名称",
    )
    model_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'chat'::character varying"),
        comment="chat | embedding",
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'openai_compatible'::character varying"),
        comment="协议，目前仅 openai_compatible",
    )
    base_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        server_default=text("''::character varying"),
        comment="OpenAI 兼容 Base URL",
    )
    api_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="API Key",
    )
    model_serve_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="传给 API 的 model 参数",
    )
    context_window: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="对话上下文长度"
    )
    max_length: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="向量输入最大长度"
    )
    dimension: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="向量维度"
    )
    features: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="对话能力：tool_call / agent_thought / image_input",
    )
    parameters: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="对话默认推理参数",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="是否为该类型默认模型",
    )
