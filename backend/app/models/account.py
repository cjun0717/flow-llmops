#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, text, Index, PrimaryKeyConstraint, Uuid
from .base_model import BaseModel

class Account(BaseModel):
    """账号模型"""
    __tablename__ = "account"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_account_id"),
        Index("account_email_idx", "email"),
        {'comment': '账号模型表'}
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="账号名称"
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="账号邮箱"
    )
    avatar: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="头像地址"
    )
    password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        server_default=text("''::character varying"),
        comment="密码哈希值"
    )
    password_salt: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        server_default=text("''::character varying"),
        comment="密码盐值"
    )
    assistant_agent_conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        comment="辅助智能体会话id"
    )
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        comment="最后登录时间"
    )
    last_login_ip: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="最后登录IP"
    )

    @property
    def is_password_set(self) -> bool:
        """只读属性，获取当前账号的密码是否设置"""
        return self.password is not None and self.password != ""

class AccountOAuth(BaseModel):
    """账号与第三方授权认证记录表"""
    __tablename__ = "account_oauth"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_account_oauth_id"),
        Index("account_oauth_account_id_idx", "account_id"),
        Index("account_oauth_openid_provider_idx", "openid", "provider"),
        {'comment': '账号与第三方授权认证记录表'}
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的账号ID"
    )
    provider: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="第三方授权提供商（如微信/谷歌）"
    )
    openid: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="第三方平台唯一标识"
    )
    encrypted_token: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="加密后的第三方token"
    )
