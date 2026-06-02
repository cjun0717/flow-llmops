#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, text, Index, PrimaryKeyConstraint, Uuid
from .base_model import BaseModel

class ApiKey(BaseModel):
    """API秘钥模型"""
    __tablename__ = "api_key"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_key_id"),
        Index("api_key_account_id_idx", "account_id"),
        Index("api_key_api_key_idx", "api_key"),
        {'comment': 'API秘钥模型表'}
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联账号ID"
    )
    api_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="加密后的API秘钥"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text('false'),
        comment="是否激活，为true时可以使用"
    )
    remark: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="备注信息"
    )
