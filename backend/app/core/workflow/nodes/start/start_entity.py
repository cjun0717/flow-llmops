#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""开始节点数据。"""
from __future__ import annotations

from pydantic import Field

from app.core.workflow.entities.node_entity import BaseNodeData
from app.core.workflow.entities.variable_entity import VariableEntity


class StartNodeData(BaseNodeData):
    """开始节点数据"""
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量信息
