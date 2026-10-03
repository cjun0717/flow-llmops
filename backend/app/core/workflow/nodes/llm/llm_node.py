#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""大语言模型节点（迁移自 imooc llm_node.py）。

从账号在前端添加的用户模型加载对话实例，在子线程中同步调用 llm.stream。
"""
from __future__ import annotations

import time
from typing import Optional

from jinja2 import Template
from langchain_core.runnables import RunnableConfig

from app.core.workflow.entities.node_entity import NodeResult, NodeStatus
from app.core.workflow.entities.workflow_entity import WorkflowState
from app.core.workflow.nodes.base_node import BaseNode
from app.core.workflow.utils.helper import extract_variables_from_state
from .llm_entity import LLMNodeData


class LLMNode(BaseNode):
    """大语言模型节点"""
    node_data: LLMNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """根据输入字段+预设 prompt 生成对应内容后输出"""
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 1.使用 jinja2 渲染模板
        template = Template(self.node_data.prompt)
        prompt_value = template.render(**inputs_dict)

        from app.services.language_model_service import LanguageModelService

        language_model_service = LanguageModelService()
        llm = language_model_service.load_language_model(self.node_data.language_model_config)

        # 3.使用 stream 代替 invoke，避免长时间未响应超时
        content = ""
        for chunk in llm.stream(prompt_value):
            content += chunk.content

        # 4.构建输出数据
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = content
        else:
            outputs["output"] = content

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
