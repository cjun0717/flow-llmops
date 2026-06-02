#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean, DateTime, Float, text, PrimaryKeyConstraint, Index, Uuid, JSON
from .base_model import BaseModel


class Workflow(BaseModel):
    """工作流模型"""
    __tablename__ = "workflow"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_id"),
        Index("workflow_account_id_idx", "account_id"),
        Index("workflow_tool_call_name_idx", "tool_call_name"),
        {'comment': '工作流模型'}
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="创建账号id"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="工作流名字"
    )
    tool_call_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="工作流工具调用名字"
    )
    icon: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="工作流图标"
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="应用描述"
    )
    graph: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        server_default=text("'{}'::json"),
        comment="运行时配置"
    )
    draft_graph: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        server_default=text("'{}'::json"),
        comment="草稿图配置"
    )
    is_debug_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="是否调试通过"
    )
    status: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="工作流状态"
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="发布时间"
    )


class WorkflowResult(BaseModel):
    """工作流存储结果模型"""
    __tablename__ = "workflow_result"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_workflow_result_id"),
        Index("workflow_result_app_id_idx", "app_id"),
        Index("workflow_result_account_id_idx", "account_id"),
        Index("workflow_result_workflow_id_idx", "workflow_id"),
        {'comment': '工作流结果模型'}
    )

    app_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        comment="工作流调用的应用id，如果为空则代表非应用调用"
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="创建账号id"
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="结果关联的工作流id"
    )
    graph: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        server_default=text("'{}'::json"),
        comment="运行时配置"
    )
    state: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        server_default=text("'{}'::json"),
        comment="工作流最终状态"
    )
    latency: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0.0"),
        comment="消息的总耗时"
    )
    status: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="运行状态"
    )
