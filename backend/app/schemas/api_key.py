#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""API 秘钥相关 Pydantic schema（迁移自 imooc api_key_schema.py）。"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.lib.helper import datetime_to_timestamp
from app.models.api_key import ApiKey


class CreateApiKeyReq(BaseModel):
    """创建 API 秘钥请求"""
    is_active: bool = Field(default=False, description="是否激活")
    remark: str = Field(default="", max_length=100, description="秘钥备注")


class UpdateApiKeyReq(BaseModel):
    """更新 API 秘钥请求"""
    is_active: bool = Field(default=False, description="是否激活")
    remark: str = Field(default="", max_length=100, description="秘钥备注")


class UpdateApiKeyIsActiveReq(BaseModel):
    """更新 API 秘钥激活状态请求"""
    is_active: bool = Field(default=False, description="是否激活")


class GetApiKeysWithPageReq(BaseModel):
    """获取 API 秘钥分页列表请求"""
    current_page: int = Field(default=1, ge=1, le=9999, description="当前页数")
    page_size: int = Field(default=20, ge=1, le=50, description="每页条数")


class GetApiKeysWithPageResp(BaseModel):
    """获取 API 秘钥分页列表响应项"""
    id: UUID = Field(default=UUID(int=0))
    api_key: str = ""
    is_active: bool = False
    remark: str = ""
    updated_at: int = 0
    created_at: int = 0

    @classmethod
    def from_model(cls, data: ApiKey) -> "GetApiKeysWithPageResp":
        return cls(
            id=data.id,
            api_key=data.api_key,
            is_active=data.is_active,
            remark=data.remark,
            updated_at=datetime_to_timestamp(data.updated_at),
            created_at=datetime_to_timestamp(data.created_at),
        )
