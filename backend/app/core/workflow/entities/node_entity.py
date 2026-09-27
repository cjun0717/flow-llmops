#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流节点实体（迁移自 imooc node_entity.py）。"""
from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NodeType(str, Enum):
    """节点类型枚举"""
    START = "start"
    LLM = "llm"
    TOOL = "tool"
    CODE = "code"
    DATASET_RETRIEVAL = "dataset_retrieval"
    HTTP_REQUEST = "http_request"
    TEMPLATE_TRANSFORM = "template_transform"
    # 意图识别分类节点
    QUESTION_CLASSIFIER = "question_classifier"
    # 迭代节点
    ITERATION = "iteration"
    END = "end"


class BaseNodeData(BaseModel):
    """基础节点数据"""
    model_config = ConfigDict(populate_by_name=True)

    class Position(BaseModel):
        """节点坐标基础模型"""
        x: float = 0
        y: float = 0

    id: UUID  # 节点id，必须唯一
    node_type: NodeType  # 节点类型
    title: str = ""  # 节点标题，必须唯一
    description: str = ""  # 节点描述信息
    position: Position = Field(default_factory=lambda: {"x": 0, "y": 0})  # 节点坐标


class NodeStatus(str, Enum):
    """节点状态"""
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeResult(BaseModel):
    """节点运行结果"""
    node_data: BaseNodeData  # 节点基础数据
    status: NodeStatus = NodeStatus.RUNNING  # 节点运行状态
    inputs: dict = Field(default_factory=dict)  # 节点输入数据
    outputs: dict = Field(default_factory=dict)  # 节点输出数据
    latency: float = 0  # 节点响应耗时
    error: str = ""  # 节点运行错误信息
