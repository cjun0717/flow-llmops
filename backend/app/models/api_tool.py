#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, text, PrimaryKeyConstraint, Index, Uuid, JSON
from .base_model import BaseModel

class ApiToolProvider(BaseModel):
    """API工具提供者模型"""
    __tablename__ = "api_tool_provider"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_tool_provider_id"),
        Index("api_tool_provider_account_id_idx", "account_id"),
        Index("api_tool_name_idx", "name"),
        {'comment': 'API工具提供者模型'}
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的账号ID"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="工具提供者名称"
    )
    icon: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="图标地址"
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="描述信息"
    )
    openapi_schema: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="OpenAPI Schema"
    )
    headers: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        server_default=text("'[]'::json"),
        comment="请求头配置"
    )



class ApiTool(BaseModel):
    """API工具表"""
    __tablename__ = "api_tool"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_tool_id"),
        Index("api_tool_account_id_idx", "account_id"),
        Index("api_tool_provider_id_name_idx", "provider_id", "name"),
        {'comment': 'API工具表'}
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的账号ID"
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的工具提供者ID"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="工具名称"
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="工具描述"
    )
    url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="API URL"
    )
    method: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="HTTP 方法"
    )
    parameters: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        server_default=text("'[]'::json"),
        comment="API 参数配置"
    )
