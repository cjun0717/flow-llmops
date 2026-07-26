#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid

from sqlalchemy import String, Text, text, PrimaryKeyConstraint, Index, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import BaseModel


class McpToolProvider(BaseModel):
    """MCP工具提供者模型"""
    __tablename__ = "mcp_tool_provider"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_mcp_tool_provider_id"),
        Index("mcp_tool_provider_account_id_idx", "account_id"),
        Index("mcp_tool_provider_name_idx", "name"),
        {"comment": "MCP工具提供者模型"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, comment="关联的账号ID")
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="提供者名称",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="描述信息",
    )
    transport: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("'http'::character varying"),
        comment="传输方式",
    )
    url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        server_default=text("''::character varying"),
        comment="MCP服务地址",
    )
    headers: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="请求头配置",
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="额外配置",
    )
    mcp_schema: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="MCP Schema",
    )


class McpTool(BaseModel):
    """MCP工具表"""
    __tablename__ = "mcp_tool"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_mcp_tool_id"),
        Index("mcp_tool_account_id_idx", "account_id"),
        Index("mcp_tool_provider_id_name_idx", "provider_id", "name"),
        {"comment": "MCP工具表"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, comment="关联的账号ID")
    provider_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, comment="提供者ID")
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="工具名称",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="描述信息",
    )
    input_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="输入参数 Schema",
    )
    tool_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="工具元数据",
    )
