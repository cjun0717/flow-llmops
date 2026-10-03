#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第三方平台 Schema（迁移自 imooc platform_schema.py）。"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class UpdateWechatConfigReq(BaseModel):
    """更新微信配置请求"""
    wechat_app_id: str = Field(default="", description="微信公众号开发者ID")
    wechat_app_secret: str = Field(default="", description="微信公众号开发者秘钥")
    wechat_token: str = Field(default="", description="微信公众号令牌")


class WechatConfigData(BaseModel):
    """获取微信配置响应"""
    app_id: UUID
    url: str = ""
    ip: str = ""
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_token: str = ""
    status: str = ""
    updated_at: int = 0
    created_at: int = 0
