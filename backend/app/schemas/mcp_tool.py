#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MCP 工具 Schema（Pydantic，迁移自 imooc mcp_tool_schema.py）。"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.lib.helper import datetime_to_timestamp
from app.models.mcp_tool import McpTool, McpToolProvider
from app.schemas.response import PageParams


JSON_SCHEMA_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
}


def transform_mcp_input_schema(input_schema: dict[str, Any]) -> list[dict[str, Any]]:
    """将 MCP JSON Schema 转换为前端已有工具参数展示结构"""
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))
    if not isinstance(properties, dict):
        return []

    inputs = []
    for name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            property_schema = {}
        json_type = property_schema.get("type", "string")
        if isinstance(json_type, list):
            json_type = next((item for item in json_type if item != "null"), "string")
        inputs.append(
            {
                "name": name,
                "type": JSON_SCHEMA_TYPE_MAP.get(json_type, "str"),
                "required": name in required,
                "description": property_schema.get("description", ""),
                "schema": property_schema,
            }
        )

    return inputs


class ValidateMcpSchemaReq(BaseModel):
    """校验 MCP 配置字符串请求"""

    mcp_schema: str = Field(..., min_length=1, description="mcp_schema字符串")


class GetMcpToolProvidersWithPageReq(PageParams):
    """获取 MCP 工具提供者分页列表请求"""

    search_word: str = Field("", description="搜索词")


class CreateMcpToolReq(BaseModel):
    """创建 MCP 工具请求"""

    mcp_schema: str = Field(..., min_length=1, description="mcp_schema字符串")


class UpdateMcpToolProviderReq(BaseModel):
    """更新 MCP 工具提供者请求"""

    mcp_schema: str = Field(..., min_length=1, description="mcp_schema字符串")


class GetMcpToolProviderResp(BaseModel):
    """获取 MCP 工具提供者响应信息"""

    id: UUID
    name: str
    description: str
    transport: str
    url: str
    headers: dict
    config: dict
    mcp_schema: str
    tools: list[dict] = Field(default_factory=list)
    updated_at: int = 0
    created_at: int = 0

    @classmethod
    def from_model(cls, data: McpToolProvider, tools: list[McpTool]) -> "GetMcpToolProviderResp":
        return cls(
            id=data.id,
            name=data.name,
            description=data.description,
            transport=data.transport,
            url=data.url,
            headers=data.headers if isinstance(data.headers, dict) else {},
            config=data.config if isinstance(data.config, dict) else {},
            mcp_schema=data.mcp_schema,
            tools=[
                {
                    "id": tool.id,
                    "name": tool.name,
                    "description": tool.description,
                    "inputs": transform_mcp_input_schema(tool.input_schema),
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ],
            updated_at=datetime_to_timestamp(data.updated_at),
            created_at=datetime_to_timestamp(data.created_at),
        )


class GetMcpToolResp(BaseModel):
    """获取 MCP 工具参数详情响应"""

    id: UUID
    name: str
    description: str
    inputs: list[dict] = Field(default_factory=list)
    input_schema: dict
    metadata: dict
    provider: dict

    @classmethod
    def from_model(cls, data: McpTool) -> "GetMcpToolResp":
        provider = data.provider
        return cls(
            id=data.id,
            name=data.name,
            description=data.description,
            inputs=transform_mcp_input_schema(data.input_schema),
            input_schema=data.input_schema if isinstance(data.input_schema, dict) else {},
            metadata=data.tool_metadata if isinstance(data.tool_metadata, dict) else {},
            provider={
                "id": provider.id,
                "name": provider.name,
                "label": provider.name,
                "icon": "",
                "description": provider.description,
                "transport": provider.transport,
                "url": provider.url,
                "headers": provider.headers if isinstance(provider.headers, dict) else {},
            },
        )


class GetMcpToolProvidersWithPageResp(BaseModel):
    """获取 MCP 工具提供者分页列表数据响应"""

    id: UUID
    name: str
    description: str
    transport: str
    url: str
    headers: dict
    tools: list[dict] = Field(default_factory=list)
    updated_at: int = 0
    created_at: int = 0

    @classmethod
    def from_model(cls, data: McpToolProvider, tools: list[McpTool]) -> "GetMcpToolProvidersWithPageResp":
        return cls(
            id=data.id,
            name=data.name,
            description=data.description,
            transport=data.transport,
            url=data.url,
            headers=data.headers if isinstance(data.headers, dict) else {},
            tools=[
                {
                    "id": tool.id,
                    "name": tool.name,
                    "description": tool.description,
                    "inputs": transform_mcp_input_schema(tool.input_schema),
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ],
            updated_at=datetime_to_timestamp(data.updated_at),
            created_at=datetime_to_timestamp(data.created_at),
        )
