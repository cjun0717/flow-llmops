#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""授权认证相关 Schema。"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from app.utils.password import password_pattern

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PasswordLoginReq(BaseModel):
    """账号密码登录请求"""

    email: str = Field(..., min_length=5, max_length=254, description="登录邮箱")
    password: str = Field(..., min_length=8, max_length=16, description="登录密码")

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        if _EMAIL_RE.match(v) is None:
            raise ValueError("登录邮箱格式错误")
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if re.match(password_pattern, v) is None:
            raise ValueError("密码最少包含一个字母，一个数字，并且长度为8-16")
        return v


class PasswordLoginData(BaseModel):
    """账号密码登录响应 data"""

    access_token: str
    expire_at: int


class OAuthAuthorizeReq(BaseModel):
    """第三方授权回调请求（stub）"""

    code: str = Field(..., min_length=1, description="第三方授权 code")


class OAuthTokenData(BaseModel):
    """第三方授权登录响应 data（与密码登录一致）"""

    access_token: str
    expire_at: int


class OAuthRedirectData(BaseModel):
    """获取第三方授权重定向地址响应 data"""

    redirect_url: str
