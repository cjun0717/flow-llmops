#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""结束节点（迁移自 imooc end_node.py）。"""
from __future__ import annotations

import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from app.core.workflow.entities.node_entity import NodeResult, NodeStatus
from app.core.workflow.entities.workflow_entity import WorkflowState
from app.core.workflow.nodes.base_node import BaseNode
from app.core.workflow.utils.helper import extract_variables_from_state
from .end_entity import EndNodeData


class EndNode(BaseNode):
    """结束节点"""
    node_data: EndNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """提取状态中需要展示的数据，并更新 outputs"""
        start_at = time.perf_counter()
        outputs_dict = extract_variables_from_state(self.node_data.outputs, state)

        return {
            "outputs": outputs_dict,
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs={},
                    outputs=outputs_dict,
                    latency=(time.perf_counter() - start_at),
                )
            ],
        }
