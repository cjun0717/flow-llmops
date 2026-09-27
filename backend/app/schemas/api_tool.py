#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""API 工具 Schema（Pydantic，迁移自 imooc api_tool_schema.py）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.lib.helper import datetime_to_timestamp
from app.models.api_tool import ApiTool, ApiToolProvider
from app.schemas.response import PageParams


def _ts(dt: datetime | None) -> int:
    return datetime_to_timestamp(dt)


class ValidateOpenAPISchemaReq(BaseModel):
    """校验 OpenAPI 规范字符串请求"""

    openapi_schema: str = Field(..., min_length=1, description="openapi_schema字符串")


class GetApiToolProvidersWithPageReq(PageParams):
    """获取 API 工具提供者分页列表请求"""

    search_word: str = Field("", description="搜索词")


class HeaderItem(BaseModel):
    """请求头项"""

    key: str
    value: str


class CreateApiToolReq(BaseModel):
    """创建自定义 API 工具请求"""

    name: str = Field(..., min_length=1, max_length=30, description="工具提供者名字")
    icon: str = Field(..., min_length=1, description="工具提供者图标URL")
    openapi_schema: str = Field(..., min_length=1, description="openapi_schema字符串")
    headers: list[HeaderItem] = Field(default_factory=list, description="请求头列表")

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, headers: list[HeaderItem]) -> list[HeaderItem]:
        return headers


class UpdateApiToolProviderReq(CreateApiToolReq):
    """更新 API 工具提供者请求（字段与创建一致）"""


class GetApiToolProviderResp(BaseModel):
    """获取 API 工具提供者响应"""

    id: UUID
    name: str
    icon: str
    openapi_schema: str
    headers: list[dict] = Field(default_factory=list)
    created_at: int = 0

    @classmethod
    def from_model(cls, data: ApiToolProvider) -> "GetApiToolProviderResp":
        return cls(
            id=data.id,
            name=data.name,
            icon=data.icon,
            openapi_schema=data.openapi_schema,
            headers=data.headers if isinstance(data.headers, list) else [],
            created_at=_ts(data.created_at),
        )


class GetApiToolResp(BaseModel):
    """获取 API 工具参数详情响应"""

    id: UUID
    name: str
    description: str
    inputs: list[dict] = Field(default_factory=list)
    provider: dict

    @classmethod
    def from_model(cls, data: ApiTool) -> "GetApiToolResp":
        provider = data.provider
        return cls(
            id=data.id,
            name=data.name,
            description=data.description,
            inputs=[
                {k: v for k, v in parameter.items() if k != "in"}
                for parameter in (data.parameters or [])
            ],
            provider={
                "id": provider.id,
                "name": provider.name,
                "icon": provider.icon,
                "description": provider.description,
                "headers": provider.headers if isinstance(provider.headers, list) else [],
            },
        )


class GetApiToolProvidersWithPageResp(BaseModel):
    """获取 API 工具提供者分页列表数据响应"""

    id: UUID
    name: str
    icon: str
    description: str
    headers: list[dict] = Field(default_factory=list)
    tools: list[dict] = Field(default_factory=list)
    created_at: int = 0

    @classmethod
    def from_model(cls, data: ApiToolProvider, tools: list[ApiTool]) -> "GetApiToolProvidersWithPageResp":
        return cls(
            id=data.id,
            name=data.name,
            icon=data.icon,
            description=data.description,
            headers=data.headers if isinstance(data.headers, list) else [],
            tools=[
                {
                    "id": tool.id,
                    "description": tool.description,
                    "name": tool.name,
                    "inputs": [
                        {k: v for k, v in parameter.items() if k != "in"}
                        for parameter in (tool.parameters or [])
                    ],
                }
                for tool in tools
            ],
            created_at=_ts(data.created_at),
        )
