#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模板转换节点（迁移自 imooc template_transform_node.py）。"""
from __future__ import annotations

import time
from typing import Optional

from jinja2 import Template
from langchain_core.runnables import RunnableConfig

from app.core.workflow.entities.node_entity import NodeResult, NodeStatus
from app.core.workflow.entities.workflow_entity import WorkflowState
from app.core.workflow.nodes.base_node import BaseNode
from app.core.workflow.utils.helper import extract_variables_from_state
from .template_transform_entity import TemplateTransformNodeData


class TemplateTransformNode(BaseNode):
    """模板转换节点，将多个变量信息合并成一个"""
    node_data: TemplateTransformNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """将传递的多个变量合并成字符串后返回"""
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        template = Template(self.node_data.template)
        template_value = template.render(**inputs_dict)

        outputs = {"output": template_value}

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
