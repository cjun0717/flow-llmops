#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, text, PrimaryKeyConstraint, Index, Uuid
from .base_model import BaseModel



class UploadFile(BaseModel):
    """上传文件模型"""
    __tablename__ = "upload_file"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_upload_file_id"),
        Index("upload_file_account_id_idx", "account_id"),
        {'comment': '上传文件表'}
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
        comment="文件名称"
    )
    key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="文件键值"
    )
    size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text('0'),
        comment="文件大小"
    )
    extension: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="文件扩展名"
    )
    mime_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="MIME类型"
    )
    hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="文件哈希值"
    )
