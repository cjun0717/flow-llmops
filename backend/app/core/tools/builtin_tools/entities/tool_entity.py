#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置工具实体（映射 {tool_name}.yaml 数据）。"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolParamType(str, Enum):
    """工具参数类型枚举"""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"


class ToolParam(BaseModel):
    """工具参数"""

    name: str
    label: str
    type: ToolParamType
    required: bool = False
    default: Optional[Any] = None
    min: Optional[float] = None
    max: Optional[float] = None
    options: list[dict[str, Any]] = Field(default_factory=list)


class ToolEntity(BaseModel):
    """工具实体类，映射 {tool_name}.yaml"""

    name: str
    label: str
    description: str
    params: list[ToolParam] = Field(default_factory=list)
