#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Python代码执行节点数据。"""
from __future__ import annotations

from pydantic import Field

from app.core.workflow.entities.node_entity import BaseNodeData
from app.core.workflow.entities.variable_entity import VariableEntity


# 默认的代码
DEFAULT_CODE = """
def main(params):
    return params
"""


class CodeNodeData(BaseNodeData):
    """Python代码执行节点数据"""
    code: str = DEFAULT_CODE  # 需要执行的Python代码
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(default_factory=list)  # 输出变量列表
