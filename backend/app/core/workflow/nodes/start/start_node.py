#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""开始节点（迁移自 imooc start_node.py）。"""
from __future__ import annotations

import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.core.workflow.entities.node_entity import NodeResult, NodeStatus
from app.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from app.core.workflow.entities.workflow_entity import WorkflowState
from app.exceptions import FailException
from app.core.workflow.nodes.base_node import BaseNode
from .start_entity import StartNodeData


class StartNode(BaseNode):
    """开始节点"""
    node_data: StartNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """提取状态中的输入信息并生成节点结果"""
        start_at = time.perf_counter()
        inputs = self.node_data.inputs

        outputs = {}
        for input in inputs:
            input_value = state["inputs"].get(input.name, None)
            if input_value is None:
                if input.required:
                    raise FailException(f"工作流参数生成出错，{input.name}为必填参数")
                else:
                    input_value = VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(input.type)
            outputs[input.name] = input_value

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=state["inputs"],
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
