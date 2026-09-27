#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模板转换节点数据。"""
from __future__ import annotations

from pydantic import Field, field_validator

from app.core.workflow.entities.node_entity import BaseNodeData
from app.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class TemplateTransformNodeData(BaseNodeData):
    """模板转换节点数据"""
    template: str = ""  # 需要拼接转换的字符串模板
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入列表
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, outputs):
        return [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED})
        ]
