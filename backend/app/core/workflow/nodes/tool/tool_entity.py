#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工具节点数据。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from app.core.workflow.entities.node_entity import BaseNodeData
from app.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class ToolNodeData(BaseNodeData):
    """工具节点数据"""
    tool_type: Literal["builtin_tool", "api_tool", "mcp_tool", ""] = Field(alias="type")  # 工具类型
    provider_id: str  # 工具提供者id
    tool_id: str  # 工具id
    params: dict = Field(default_factory=dict)  # 内置工具设置参数
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED})
        ]
    )  # 输出字段列表

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, outputs):
        return [
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED})
        ]
