#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流节点基类（迁移自 imooc base_node.py）。"""
from __future__ import annotations

from abc import ABC

from langchain_core.runnables import RunnableSerializable

from app.core.workflow.entities.node_entity import BaseNodeData


class BaseNode(RunnableSerializable, ABC):
    """工作流节点基类"""
    node_data: BaseNodeData
