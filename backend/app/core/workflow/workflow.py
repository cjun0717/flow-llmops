#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流 LangChain 工具类（迁移自 imooc workflow.py）。

将草稿/运行时图配置编译为 LangGraph 图程序，并包装为 LangChain BaseTool，
供 Agent 作为工具调用，或供调试接口流式输出节点结果。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Iterator, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Input, Output
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field, PrivateAttr, create_model

from app.core.workflow.entities.node_entity import BaseNodeData, NodeResult, NodeStatus, NodeType
from app.core.workflow.entities.variable_entity import VARIABLE_TYPE_MAP
from app.core.workflow.entities.workflow_entity import WorkflowConfig, WorkflowState
from app.core.workflow.nodes import (
    DatasetRetrievalNode,
    EndNode,
    HttpRequestNode,
    IterationNode,
    LLMNode,
    QuestionClassifierNode,
    QuestionClassifierNodeData,
    StartNode,
    TemplateTransformNode,
    ToolNode,
    CodeNode,
)
from app.exceptions import FailException, ValidateException


# 节点类映射
NodeClasses = {
    NodeType.START: StartNode,
    NodeType.END: EndNode,
    NodeType.LLM: LLMNode,
    NodeType.TEMPLATE_TRANSFORM: TemplateTransformNode,
    NodeType.DATASET_RETRIEVAL: DatasetRetrievalNode,
    NodeType.CODE: CodeNode,
    NodeType.TOOL: ToolNode,
    NodeType.HTTP_REQUEST: HttpRequestNode,
    NodeType.QUESTION_CLASSIFIER: QuestionClassifierNode,
    NodeType.ITERATION: IterationNode,
}


class Workflow(BaseTool):
    """工作流 LangChain 工具类"""
    _workflow_config: WorkflowConfig = PrivateAttr(None)
    _workflow: CompiledStateGraph = PrivateAttr(None)

    def __init__(self, workflow_config: WorkflowConfig, **kwargs: Any):
        """构造函数，完成工作流函数的初始化"""
        super().__init__(
            name=workflow_config.name,
            description=workflow_config.description,
            args_schema=self._build_args_schema(workflow_config),
            **kwargs,
        )
        self._workflow_config = workflow_config
        self._workflow = self._build_workflow()

    @classmethod
    def _build_args_schema(cls, workflow_config: WorkflowConfig) -> type[BaseModel]:
        """构建输入参数结构体"""
        fields = {}
        inputs = next(
            (node.inputs for node in workflow_config.nodes if node.node_type == NodeType.START),
            [],
        )

        for input in inputs:
            field_name = input.name
            field_type = VARIABLE_TYPE_MAP.get(input.type, str)
            field_required = input.required
            field_description = input.description
            field_default = ... if field_required else None

            fields[field_name] = (
                field_type if field_required else Optional[field_type],
                Field(default=field_default, description=field_description),
            )

        return create_model("DynamicModel", **fields)

    @staticmethod
    def _wrap_runtime_node(node_data: BaseNodeData, runnable: Any):
        """包装真实执行节点，让节点异常也能以调试结果形式输出到前端。"""

        def invoke_node(state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
            start_at = time.perf_counter()
            try:
                return runnable.invoke(state, config=config)
            except Exception as error:
                log_context = {"node_id": node_data.id, "error": error}
                if isinstance(error, (FailException, ValidateException)):
                    logging.warning("工作流节点运行失败, node_id=%(node_id)s, error=%(error)s", log_context)
                else:
                    logging.exception("工作流节点运行失败, node_id=%(node_id)s, error=%(error)s", log_context)
                message = getattr(error, "message", None) or str(error) or "节点运行失败"
                return {
                    "node_results": [
                        NodeResult(
                            node_data=node_data,
                            status=NodeStatus.FAILED,
                            inputs=state.get("inputs", {}),
                            outputs={},
                            latency=(time.perf_counter() - start_at),
                            error=message,
                        )
                    ]
                }

        return invoke_node

    def _build_workflow(self) -> CompiledStateGraph:
        """构建编译后的工作流图程序"""
        # 1.创建 graph 图程序结构
        graph = StateGraph(WorkflowState)

        # 2.提取 nodes 和 edges 信息
        nodes = self._workflow_config.nodes
        edges = self._workflow_config.edges

        # 3.循环遍历 nodes 节点添加节点
        for node in nodes:
            node_flag = f"{node.node_type.value}_{node.id}"
            if node.node_type == NodeType.START:
                graph.add_node(
                    node_flag,
                    self._wrap_runtime_node(node, NodeClasses[NodeType.START](node_data=node)),
                )
            elif node.node_type == NodeType.LLM:
                graph.add_node(
                    node_flag,
                    self._wrap_runtime_node(node, NodeClasses[NodeType.LLM](node_data=node)),
                )
            elif node.node_type == NodeType.TEMPLATE_TRANSFORM:
                graph.add_node(
                    node_flag,
                    self._wrap_runtime_node(node, NodeClasses[NodeType.TEMPLATE_TRANSFORM](node_data=node)),
                )
            elif node.node_type == NodeType.DATASET_RETRIEVAL:
                graph.add_node(
                    node_flag,
                    self._wrap_runtime_node(
                        node,
                        NodeClasses[NodeType.DATASET_RETRIEVAL](
                            account_id=self._workflow_config.account_id,
                            node_data=node,
                        ),
                    ),
                )
            elif node.node_type == NodeType.CODE:
                graph.add_node(
                    node_flag,
                    self._wrap_runtime_node(node, NodeClasses[NodeType.CODE](node_data=node)),
                )
            elif node.node_type == NodeType.TOOL:
                graph.add_node(
                    node_flag,
                    self._wrap_runtime_node(node, NodeClasses[NodeType.TOOL](node_data=node)),
                )
            elif node.node_type == NodeType.HTTP_REQUEST:
                graph.add_node(
                    node_flag,
                    self._wrap_runtime_node(node, NodeClasses[NodeType.HTTP_REQUEST](node_data=node)),
                )
            elif node.node_type == NodeType.END:
                graph.add_node(
                    node_flag,
                    self._wrap_runtime_node(node, NodeClasses[NodeType.END](node_data=node)),
                )
            elif node.node_type == NodeType.QUESTION_CLASSIFIER:
                # 4.问题分类节点为条件边对应的节点，添加虚拟起始节点返回空字典
                graph.add_node(
                    node_flag,
                    lambda state: {"node_results": []}
                )
                # 4.1 为每个分类添加虚拟终止节点
                assert isinstance(node, QuestionClassifierNodeData)
                for item in node.classes:
                    graph.add_node(
                        f"qc_source_handle_{str(item.source_handle_id)}",
                        lambda state: {"node_results": []}
                    )
                # 4.2 将虚拟起点和终点用条件边拼接
                graph.add_conditional_edges(
                    node_flag,
                    NodeClasses[NodeType.QUESTION_CLASSIFIER](
                        account_id=self._workflow_config.account_id,
                        node_data=node,
                    )
                )
            elif node.node_type == NodeType.ITERATION:
                graph.add_node(
                    node_flag,
                    self._wrap_runtime_node(node, NodeClasses[NodeType.ITERATION](node_data=node))
                )
            else:
                raise ValidateException("工作流节点类型错误，请核实后重试")

        # 5.循环遍历 edges 添加边
        parallel_edges = {}  # key:终点，value:起点列表
        start_node = ""
        end_node = ""
        non_parallel_nodes = []  # 不能并行执行的节点（意图节点虚拟起点和终点）
        for edge in edges:
            # 6.计算并获取并行边
            source_node = f"{edge.source_type.value}_{edge.source}"
            target_node = f"{edge.target_type.value}_{edge.target}"

            # 7.处理特殊节点类型边信息（意图识别）
            if edge.source_type == NodeType.QUESTION_CLASSIFIER:
                source_node = f"qc_source_handle_{str(edge.source_handle_id)}"
                non_parallel_nodes.extend([source_node, target_node])

            # 8.处理并行节点
            if target_node not in parallel_edges:
                parallel_edges[target_node] = [source_node]
            else:
                parallel_edges[target_node].append(source_node)

            # 9.检测特殊节点（开始/结束）
            if edge.source_type == NodeType.START:
                start_node = f"{edge.source_type.value}_{edge.source}"
            if edge.target_type == NodeType.END:
                end_node = f"{edge.target_type.value}_{edge.target}"

        # 10.设置开始和终点
        graph.set_entry_point(start_node)
        graph.set_finish_point(end_node)

        # 11.循环遍历合并边
        for target_node, source_nodes in parallel_edges.items():
            # 11.1 循环遍历意图识别节点的下一条边并单独添加
            source_nodes_tmp = [*source_nodes]
            for item in non_parallel_nodes:
                if item in source_nodes_tmp:
                    source_nodes_tmp.remove(item)
                    graph.add_edge(item, target_node)
            # 11.2 正常添加其他边
            graph.add_edge(source_nodes_tmp, target_node)

        # 12.构建图程序并编译
        return graph.compile()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """工作流组件基础 run 方法"""
        result = self._workflow.invoke({"inputs": kwargs})
        return result.get("outputs", {})

    def stream(
        self,
        input: Input,
        config: Optional[RunnableConfig] = None,
        **kwargs: Optional[Any],
    ) -> Iterator[Output]:
        """工作流流式输出每个节点对应的结果"""
        return self._workflow.stream({"inputs": input})
