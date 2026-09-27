#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库检索节点数据。"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.workflow.entities.node_entity import BaseNodeData
from app.core.workflow.entities.variable_entity import VariableEntity, VariableType, VariableValueType
from app.entities.dataset_entity import RetrievalStrategy
from app.exceptions import FailException


class RetrievalConfig(BaseModel):
    """检索配置"""
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC  # 检索策略
    k: int = 4  # 最大召回数量
    score: float = 0  # 得分阈值


class DatasetRetrievalNodeData(BaseNodeData):
    """知识库检索节点数据"""
    dataset_ids: list[UUID]  # 关联的知识库id列表
    retrieval_config: RetrievalConfig = Field(default_factory=RetrievalConfig)  # 检索配置
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量信息
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="combine_documents", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, value):
        return [
            VariableEntity(name="combine_documents", value={"type": VariableValueType.GENERATED})
        ]

    @field_validator("inputs")
    @classmethod
    def validate_inputs(cls, value):
        """校验输入变量信息"""
        if len(value) != 1:
            raise FailException("知识库节点输入变量信息出错")
        query_input = value[0]
        if query_input.name != "query" or query_input.type != VariableType.STRING or query_input.required is False:
            raise FailException("知识库节点输入变量名字/变量类型/必填属性出错")
        return value
