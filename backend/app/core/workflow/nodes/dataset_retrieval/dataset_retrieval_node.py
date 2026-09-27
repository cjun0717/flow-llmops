#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库检索节点（迁移自 imooc dataset_retrieval_node.py）。

适配 FastAPI：通过 deps 中的 lru_cache 单例访问器构建 RetrievalService，
检索工具在子线程中用 asyncio.run + 全新 AsyncSession 执行异步检索。
"""
from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

from pydantic import PrivateAttr
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from app.core.workflow.entities.node_entity import NodeResult, NodeStatus
from app.core.workflow.entities.workflow_entity import WorkflowState
from app.core.workflow.nodes.base_node import BaseNode
from app.core.workflow.utils.helper import extract_variables_from_state
from .dataset_retrieval_entity import DatasetRetrievalNodeData


class DatasetRetrievalNode(BaseNode):
    """知识库检索节点"""
    node_data: DatasetRetrievalNodeData
    _retrieval_tool: BaseTool = PrivateAttr(None)

    def __init__(self, *args: Any, account_id: UUID, **kwargs: Any):
        """构造函数，完成知识库检索节点的初始化"""
        super().__init__(*args, **kwargs)

        # 1.通过 lru_cache 单例访问器构建检索服务
        from app.deps import get_jieba_service, get_vector_database_service
        from app.services.retrieval_service import RetrievalService

        retrieval_service = RetrievalService(get_jieba_service(), get_vector_database_service())

        # 2.构建检索服务工具
        self._retrieval_tool = retrieval_service.create_langchain_tool_from_search(
            dataset_ids=self.node_data.dataset_ids,
            account_id=account_id,
            **self.node_data.retrieval_config.model_dump(),
        )

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """执行知识库检索后返回"""
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        combine_documents = self._retrieval_tool.invoke(inputs_dict)

        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = combine_documents
        else:
            outputs["combine_documents"] = combine_documents

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
