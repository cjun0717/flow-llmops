#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""迭代节点（迁移自 imooc iteration_node.py）。

适配 FastAPI：子工作流记录查询在子线程中用 asyncio.run + 全新 AsyncSession 执行。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig

from app.core.workflow.entities.node_entity import NodeResult, NodeStatus
from app.core.workflow.entities.workflow_entity import WorkflowState, WorkflowConfig
from app.core.workflow.nodes.base_node import BaseNode
from app.core.workflow.utils.helper import extract_variables_from_state
from app.entities.workflow_entity import WorkflowStatus
from .iteration_entity import IterationNodeData


class IterationNode(BaseNode):
    """迭代节点"""
    node_data: IterationNodeData
    workflow: Any = None

    def __init__(self, *args: Any, **kwargs: Any):
        """构造函数，完成数据的初始化"""
        try:
            super().__init__(*args, **kwargs)

            if len(self.node_data.workflow_ids) != 1:
                self.workflow = None
            else:
                # 1.查询工作流记录（子线程中用 asyncio.run）
                from app.db import AsyncSessionLocal
                from app.models.workflow import Workflow
                from sqlalchemy import select

                async def _query():
                    async with AsyncSessionLocal() as db:
                        result = await db.execute(
                            select(Workflow).where(Workflow.id == self.node_data.workflow_ids[0])
                        )
                        return result.scalar_one_or_none()

                workflow_record = self._run_sync(_query())

                if not workflow_record or workflow_record.status != WorkflowStatus.PUBLISHED:
                    self.workflow = None
                else:
                    # 2.已发布且存在，构建工作流工具
                    from app.core.workflow.workflow import Workflow as WorkflowTool
                    self.workflow = WorkflowTool(
                        workflow_config=WorkflowConfig(
                            account_id=workflow_record.account_id,
                            name="iteration_workflow",
                            description=self.node_data.description,
                            nodes=workflow_record.graph.get("nodes", []),
                            edges=workflow_record.graph.get("edges", []),
                        )
                    )
        except Exception as error:
            logging.error("迭代节点子工作流构建失败: %s", error, exc_info=True)
            self.workflow = None

    @staticmethod
    def _run_sync(coro):
        from app.core.workflow.utils.db_helper import run_sync
        return run_sync(coro)

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """循环遍历将工作流的结果进行输出"""
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)
        inputs = inputs_dict.get("inputs", [])

        # 1.异常检测
        if (
            self.workflow is None
            or len(self.workflow.args) != 1
            or not isinstance(inputs, list)
            or len(inputs) == 0
        ):
            return {
                "node_results": [
                    NodeResult(
                        node_data=self.node_data,
                        status=NodeStatus.FAILED,
                        inputs=inputs_dict,
                        outputs={"outputs": []},
                        latency=(time.perf_counter() - start_at),
                    )
                ]
            }

        # 2.获取工作流输入字段结构
        param_key = list(self.workflow.args.keys())[0]

        # 3.循环遍历输入数据调用迭代工作流
        outputs = []
        for item in inputs:
            data = {param_key: item}
            iteration_result = self.workflow.invoke(data)
            outputs.append(json.dumps(iteration_result, ensure_ascii=False))

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs={"outputs": outputs},
                    latency=(time.perf_counter() - start_at),
                )
            ]
        }
