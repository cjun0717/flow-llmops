#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, text, PrimaryKeyConstraint, Index, Uuid
from .base_model import BaseModel

class WechatConfig(BaseModel):
    """Agent微信配置信息"""
    __tablename__ = "wechat_config"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_wechat_config_id"),
        Index("wechat_config_app_id_idx", "app_id"),
        {'comment': '微信配置信息'}
    )

    app_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="配置关联应用id"
    )
    wechat_app_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        server_default=text("''::character varying"),
        comment="微信公众号开发者id"
    )
    wechat_app_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        server_default=text("''::character varying"),
        comment="微信公众号开发者秘钥"
    )
    wechat_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        server_default=text("''::character varying"),
        comment="微信公众号校验凭证"
    )
    status: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''::character varying"),
        comment="配置状态"
    )


class WechatEndUser(BaseModel):
    """微信公众号与终端用户标识关联表"""
    __tablename__ = "wechat_end_user"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_wechat_end_user_id"),
        Index("wechat_end_user_openid_app_id_idx", "openid", "app_id"),
        {'comment': '微信公众号与终端用户关联表'}
    )

    openid: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="发送方账号，数据其实是openid(FromUserName/source)"
    )
    app_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联配置的应用id"
    )
    end_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的终端用户id"
    )

class WechatMessage(BaseModel):
    """微信公众号消息模型，用于记录未推送的消息记录"""
    __tablename__ = "wechat_message"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_wechat_message_id"),
        Index("wechat_message_wechat_end_user_id_idx", "wechat_end_user_id"),
        {'comment': '微信公众号消息记录表'}
    )

    wechat_end_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的微信终端用户id"
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="关联的消息id"
    )
    is_pushed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="是否推送，默认为false表示未推送"
    )
