#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MCP 工具实体。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class McpToolEntity(BaseModel):
    """MCP 工具实体信息，记录创建 LangChain 工具所需的配置"""

    provider_id: str = Field(default="", description="MCP工具提供者id")
    name: str = Field(default="", description="MCP工具原始名称")
    description: str = Field(default="", description="MCP工具描述")
    url: str = Field(default="", description="MCP Streamable HTTP endpoint")
    headers: dict[str, str] = Field(default_factory=dict, description="MCP HTTP headers")
    input_schema: dict = Field(default_factory=dict, description="MCP工具输入JSON Schema")
    metadata: dict = Field(default_factory=dict, description="MCP工具元数据")
