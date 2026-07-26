#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, text, PrimaryKeyConstraint, Index, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from .base_model import BaseModel

class App(BaseModel):
    """AI应用基础模型类"""
    __tablename__ = "app"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_id"),
        Index("app_account_id_idx", "account_id"),
        Index("app_token_idx", "token"),
        {'comment': 'AI应用基础模型类'}
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="创建账号id"
    )
    app_config_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        comment="发布配置id，当值为空时代表没有发布"
    )
    draft_app_config_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        comment="关联的草稿配置id"
    )
    debug_conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        comment="应用调试会话id，为None则代表没有会话信息"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="应用名字"
    )
    icon: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="应用图标"
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="应用描述"
    )
    token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        server_default=text("''::character varying"),
        comment="应用凭证信息"
    )
    status: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="应用状态"
    )


class AppConfig(BaseModel):
    """应用配置模型"""
    __tablename__ = "app_config"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_id"),
        Index("app_config_app_id_idx", "app_id"),
        {'comment': '应用配置模型'}
    )

    app_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联应用id"
    )
    model_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="模型配置"
    )
    dialog_round: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="鞋带上下文轮数"
    )
    preset_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="预设prompt"
    )
    tools: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="应用关联工具列表"
    )
    workflows: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="应用关联的工作流列表"
    )
    retrieval_config: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="检索配置"
    )
    long_term_memory: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="长期记忆配置"
    )
    opening_statement: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="开场白文案"
    )
    opening_questions: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="开场白建议问题列表"
    )
    speech_to_text: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="语音转文本配置"
    )
    text_to_speech: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="文本转语音配置"
    )
    suggested_after_answer: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
        comment="回答后生成建议问题"
    )
    review_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="审核配置"
    )


class AppConfigVersion(BaseModel):
    """应用配置版本历史表，用于存储草稿配置+历史发布配置"""
    __tablename__ = "app_config_version"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_config_version_id"),
        Index("app_config_version_app_id_idx", "app_id"),
        {'comment': '应用配置版本历史表'}
    )

    app_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联应用id"
    )
    model_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="模型配置"
    )
    dialog_round: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="鞋带上下文轮数"
    )
    preset_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="人设与回复逻辑"
    )
    tools: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="应用关联的工具列表"
    )
    workflows: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="应用关联的工作流列表"
    )
    datasets: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="应用关联的知识库列表"
    )
    retrieval_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="检索配置"
    )
    long_term_memory: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="长期记忆配置"
    )
    opening_statement: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="开场白文案"
    )
    opening_questions: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="开场白建议问题列表"
    )
    speech_to_text: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="语音转文本配置"
    )
    text_to_speech: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="文本转语音配置"
    )
    suggested_after_answer: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{\"enable\": true}'::jsonb"),
        comment="回答后生成建议问题"
    )
    review_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="审核配置"
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="发布版本号"
    )
    config_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="配置类型"
    )


class AppDatasetJoin(BaseModel):
    """应用知识库关联表模型"""
    __tablename__ = "app_dataset_join"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_app_dataset_join_id"),
        Index("app_dataset_join_app_id_dataset_id_idx", "app_id", "dataset_id"),
        {'comment': '应用知识库关联表'}
    )

    app_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="应用ID"
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="知识库ID"
    )
