#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HTTP请求节点（迁移自 imooc http_request_node.py）。"""
from __future__ import annotations

import time
from typing import Optional

import requests
from langchain_core.runnables import RunnableConfig

from app.core.workflow.entities.node_entity import NodeResult, NodeStatus
from app.core.workflow.entities.workflow_entity import WorkflowState
from app.core.workflow.nodes.base_node import BaseNode
from app.core.workflow.utils.helper import extract_variables_from_state
from .http_request_entity import (
    HttpRequestInputType,
    HttpRequestMethod,
    HttpRequestNodeData,
)


class HttpRequestNode(BaseNode):
    """HTTP请求节点"""
    node_data: HttpRequestNodeData

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """向指定的URL发起请求并获取响应"""
        start_at = time.perf_counter()
        _inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 1.按 params/headers/body 分组
        inputs_dict = {
            HttpRequestInputType.PARAMS: {},
            HttpRequestInputType.HEADERS: {},
            HttpRequestInputType.BODY: {},
        }
        for input in self.node_data.inputs:
            inputs_dict[input.meta.get("type")][input.name] = _inputs_dict.get(input.name)

        # 2.请求方法映射
        request_methods = {
            HttpRequestMethod.GET: requests.get,
            HttpRequestMethod.POST: requests.post,
            HttpRequestMethod.PUT: requests.put,
            HttpRequestMethod.PATCH: requests.patch,
            HttpRequestMethod.DELETE: requests.delete,
            HttpRequestMethod.HEAD: requests.head,
            HttpRequestMethod.OPTIONS: requests.options,
        }

        request_method = request_methods[self.node_data.method]
        request_url = str(self.node_data.url) if self.node_data.url else ""
        if self.node_data.method == HttpRequestMethod.GET:
            response = request_method(
                request_url,
                headers=inputs_dict[HttpRequestInputType.HEADERS],
                params=inputs_dict[HttpRequestInputType.PARAMS],
            )
        else:
            response = request_method(
                request_url,
                headers=inputs_dict[HttpRequestInputType.HEADERS],
                params=inputs_dict[HttpRequestInputType.PARAMS],
                data=inputs_dict[HttpRequestInputType.BODY],
            )

        text = response.text
        status_code = response.status_code

        outputs = {"text": text, "status_code": status_code}

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
