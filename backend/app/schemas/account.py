#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""账号设置相关 Schema。"""
from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.account import Account
from app.utils.password import password_pattern


def datetime_to_timestamp(dt: datetime | None) -> int:
    """datetime → 秒级时间戳"""
    if dt is None:
        return 0
    return int(dt.timestamp())


class AccountInfoData(BaseModel):
    """当前登录账号信息"""

    id: UUID
    name: str
    email: str
    avatar: str
    last_login_at: int
    last_login_ip: str
    created_at: int

    @classmethod
    def from_model(cls, account: Account) -> AccountInfoData:
        return cls(
            id=account.id,
            name=account.name,
            email=account.email,
            avatar=account.avatar,
            last_login_at=datetime_to_timestamp(account.last_login_at),
            last_login_ip=account.last_login_ip,
            created_at=datetime_to_timestamp(account.created_at),
        )


class UpdatePasswordReq(BaseModel):
    """修改密码请求"""

    password: str = Field(..., min_length=8, max_length=16, description="新密码")

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if re.match(password_pattern, v) is None:
            raise ValueError("密码最少包含一个字母、一个数字，并且长度是8-16")
        return v


class UpdateNameReq(BaseModel):
    """修改账号名称请求"""

    name: str = Field(..., min_length=3, max_length=30, description="账号名称")


class UpdateAvatarReq(BaseModel):
    """修改账号头像请求"""

    avatar: str = Field(..., min_length=1, description="头像 URL")

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("账号头像必须是URL图片地址")
        return v
