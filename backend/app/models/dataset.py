#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, Boolean, DateTime, text, PrimaryKeyConstraint, Index, Uuid, JSON
from .base_model import BaseModel



class Dataset(BaseModel):
    """知识库表"""
    __tablename__ = "dataset"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_dataset_id"),
        Index("dataset_account_id_name_idx", "account_id", "name"),
        {'comment': '知识库表'}
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
        comment="知识库名称"
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


class Document(BaseModel):
    """文档表模型"""
    __tablename__ = "document"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_document_id"),
        Index("document_account_id_idx", "account_id"),
        Index("document_dataset_id_idx", "dataset_id"),
        Index("document_batch_idx", "batch"),
        {'comment': '文档表'}
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的账号ID"
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的知识库ID"
    )
    upload_file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="上传文件ID"
    )
    process_rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="处理规则ID"
    )
    batch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="批次号"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="文档名称"
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="位置"
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="字符数"
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="token数"
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="处理开始时间"
    )
    parsing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="解析完成时间"
    )
    splitting_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="分割完成时间"
    )
    indexing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="索引完成时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="完成时间"
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="停止时间"
    )
    error: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="错误信息"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="是否启用"
    )
    disabled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="禁用时间"
    )
    status: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("'waiting'::character varying"),
        comment="状态"
    )

class Segment(BaseModel):
    """片段表模型"""
    __tablename__ = "segment"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_segment_id"),
        Index("segment_account_id_idx", "account_id"),
        Index("segment_dataset_id_idx", "dataset_id"),
        Index("segment_document_id_idx", "document_id"),
        {'comment': '片段表'}
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的账号ID"
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的知识库ID"
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的文档ID"
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="节点ID"
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="位置"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="内容"
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="字符数"
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="token数"
    )
    keywords: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        server_default=text("'[]'::json"),
        comment="关键词列表"
    )
    hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="哈希值"
    )
    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="命中次数"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="是否启用"
    )
    disabled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="禁用时间"
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="处理开始时间"
    )
    indexing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="索引完成时间"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="完成时间"
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="停止时间"
    )
    error: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="错误信息"
    )
    status: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("'waiting'::character varying"),
        comment="状态"
    )


class KeywordTable(BaseModel):
    """关键词表模型"""
    __tablename__ = "keyword_table"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_keyword_table_id"),
        Index("keyword_table_dataset_id_idx", "dataset_id"),
        {'comment': '关键词表'}
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的知识库ID"
    )
    keyword_table: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        server_default=text("'{}'::json"),
        comment="关键词表"
    )


class DatasetQuery(BaseModel):
    """知识库查询表模型"""
    __tablename__ = "dataset_query"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_dataset_query_id"),
        Index("dataset_query_dataset_id_idx", "dataset_id"),
        Index("dataset_created_by_idx", "created_by"),
        Index("dataset_source_app_id_idx", "source_app_id"),
        {'comment': '知识库查询表'}
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的知识库ID"
    )
    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''::text"),
        comment="查询内容"
    )
    source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("'HitTesting'::character varying"),
        comment="来源"
    )
    source_app_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        comment="来源应用ID"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        comment="创建者ID"
    )


class ProcessRule(BaseModel):
    """文档处理规则表模型"""
    __tablename__ = "process_rule"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_process_rule_id"),
        Index("process_rule_account_id_idx", "account_id"),
        Index("process_rule_dataset_id_idx", "dataset_id"),
        {'comment': '文档处理规则表'}
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的账号ID"
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的知识库ID"
    )
    mode: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("'automic'::character varying"),
        comment="模式"
    )
    rule: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        server_default=text("'{}'::json"),
        comment="规则"
    )
