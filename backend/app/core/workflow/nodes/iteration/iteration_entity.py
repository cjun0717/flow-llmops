#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""迭代节点数据。"""
from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from app.core.workflow.entities.node_entity import BaseNodeData
from app.core.workflow.entities.variable_entity import VariableEntity, VariableType, VariableValueType
from app.exceptions import FailException


class IterationNodeData(BaseNodeData):
    """迭代节点数据"""
    workflow_ids: list[UUID]  # 需要迭代的工作流id
    inputs: list[VariableEntity] = Field(default_factory=lambda: [
        VariableEntity(
            name="inputs",
            type=VariableType.LIST_STRING,
            value={"type": VariableValueType.LITERAL, "content": []}
        )
    ])  # 输入变量列表
    outputs: list[VariableEntity] = Field(default_factory=list)

    @field_validator("workflow_ids")
    @classmethod
    def validate_workflow_ids(cls, value):
        """校验迭代的工作流数量是否小于等于1"""
        if len(value) > 1:
            raise FailException("迭代节点只能绑定一个工作流")
        return value

    @field_validator("inputs")
    @classmethod
    def validate_inputs(cls, value):
        """校验输入变量是否正确"""
        if len(value) != 1:
            raise FailException("迭代节点输入变量信息错误")
        iteration_inputs = value[0]
        allow_types = [
            VariableType.LIST_STRING,
            VariableType.LIST_INT,
            VariableType.LIST_FLOAT,
            VariableType.LIST_BOOLEAN,
        ]
        if (
            iteration_inputs.name != "inputs"
            or iteration_inputs.type not in allow_types
            or iteration_inputs.required is False
        ):
            raise FailException("迭代节点输入变量名字/类型/必填属性出错")
        return value

    @field_validator("outputs")
    @classmethod
    def validate_outputs(cls, value):
        """固定节点输出为列表型字符串，将工作流所有结果迭代存储到该列表"""
        return [
            VariableEntity(name="outputs", value={"type": VariableValueType.GENERATED})
        ]
