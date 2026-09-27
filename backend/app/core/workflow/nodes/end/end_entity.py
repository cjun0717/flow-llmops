#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""结束节点数据。"""
from __future__ import annotations

from pydantic import Field

from app.core.workflow.entities.node_entity import BaseNodeData
from app.core.workflow.entities.variable_entity import VariableEntity


class EndNodeData(BaseNodeData):
    """结束节点数据"""
    outputs: list[VariableEntity] = Field(default_factory=list)  # 结束节点需要输出的数据
