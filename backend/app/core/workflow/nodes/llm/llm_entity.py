#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""大语言模型节点数据。"""
from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from app.core.workflow.entities.node_entity import BaseNodeData
from app.core.workflow.entities.variable_entity import VariableEntity, VariableValueType
from app.entities.app_entity import DEFAULT_APP_CONFIG


class LLMNodeData(BaseNodeData):
    """大语言模型节点数据"""
    prompt: str  # 提示词
    language_model_config: dict = Field(
        alias="model_config",
        default_factory=lambda: DEFAULT_APP_CONFIG["model_config"],
    )  # 大语言模型配置信息
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入列表
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, value):
        return [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED})
        ]
