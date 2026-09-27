#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流相关枚举与常量（对齐 imooc workflow_entity.py）。"""
from __future__ import annotations

from enum import Enum


class WorkflowStatus(str, Enum):
    """工作流状态类型枚举"""

    DRAFT = "draft"
    PUBLISHED = "published"


class WorkflowResultStatus(str, Enum):
    """工作流运行结果状态"""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# 工作流默认配置信息
DEFAULT_WORKFLOW_CONFIG = {
    "graph": {},
    "draft_graph": {
        "nodes": [],
        "edges": [],
    },
}
