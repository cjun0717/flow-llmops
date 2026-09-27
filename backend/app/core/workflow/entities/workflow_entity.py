#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流配置实体（迁移自 imooc workflow_entity.py）。

包含 WorkflowConfig（草稿/运行时图配置校验）与 WorkflowState（LangGraph 状态）。
"""
from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Annotated, Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.exceptions import ValidateException
from .edge_entity import BaseEdgeData
from .node_entity import BaseNodeData, NodeResult, NodeType
from .variable_entity import VariableEntity, VariableValueType


# 工作流配置校验信息
WORKFLOW_CONFIG_NAME_PATTERN = r'^[A-Za-z_][A-Za-z0-9_]*$'
WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH = 1024


def _process_dict(left: dict, right: dict) -> dict:
    """工作流状态字典归纳函数"""
    left = left or {}
    right = right or {}
    return {**left, **right}


def _process_node_results(left: list, right: list) -> list:
    """工作流状态节点结果列表归纳函数"""
    left = left or []
    right = right or []
    return left + right


class WorkflowConfig(BaseModel):
    """工作流配置信息"""
    account_id: UUID  # 用户唯一标识
    name: str = ""  # 工作流名称，必须是英文
    description: str = ""  # 工作流描述信息，告知 LM 何时调用工作流
    nodes: list[BaseNodeData] = Field(default_factory=list)  # 节点列表
    edges: list[BaseEdgeData] = Field(default_factory=list)  # 边列表

    @model_validator(mode="before")
    @classmethod
    def validate_workflow_config(cls, values: dict):
        """自定义校验函数，校验工作流配置中的所有参数"""
        # 1.校验工作流名字
        name = values.get("name", None)
        if not name or not re.match(WORKFLOW_CONFIG_NAME_PATTERN, name):
            raise ValidateException("工作流名字仅支持字母、数字和下划线，且以字母/下划线为开头")

        # 2.校验描述信息长度
        description = values.get("description", None)
        if not description or len(description) > WORKFLOW_CONFIG_DESCRIPTION_MAX_LENGTH:
            raise ValidateException("工作流描述信息长度不能超过1024个字符")

        # 3.获取节点和边列表
        nodes = values.get("nodes", [])
        edges = values.get("edges", [])

        # 4.校验 nodes/edges 类型与非空
        if not isinstance(nodes, list) or len(nodes) <= 0:
            raise ValidateException("工作流节点列表信息错误，请核实后重试")
        if not isinstance(edges, list) or len(edges) <= 0:
            raise ValidateException("工作流边列表信息错误，请核实后重试")

        # 5.节点数据类映射（延迟导入避免循环依赖）
        from app.core.workflow.nodes import (
            CodeNodeData,
            DatasetRetrievalNodeData,
            EndNodeData,
            HttpRequestNodeData,
            LLMNodeData,
            StartNodeData,
            TemplateTransformNodeData,
            ToolNodeData,
            QuestionClassifierNodeData,
            IterationNodeData,
        )
        node_data_classes = {
            NodeType.START: StartNodeData,
            NodeType.END: EndNodeData,
            NodeType.LLM: LLMNodeData,
            NodeType.TEMPLATE_TRANSFORM: TemplateTransformNodeData,
            NodeType.DATASET_RETRIEVAL: DatasetRetrievalNodeData,
            NodeType.CODE: CodeNodeData,
            NodeType.TOOL: ToolNodeData,
            NodeType.HTTP_REQUEST: HttpRequestNodeData,
            NodeType.QUESTION_CLASSIFIER: QuestionClassifierNodeData,
            NodeType.ITERATION: IterationNodeData,
        }

        # 6.循环遍历所有节点
        node_data_dict: dict = {}
        start_nodes = 0
        end_nodes = 0
        for node in nodes:
            if not isinstance(node, dict):
                raise ValidateException("工作流节点数据类型出错，请核实后重试")

            node_type = node.get("node_type", "")
            node_data_cls = node_data_classes.get(node_type, None)
            if not node_data_cls:
                raise ValidateException("工作流节点类型出错，请核实后重试")

            node_data = node_data_cls(**node)

            # 7.判断开始/结束节点是否唯一
            if node_data.node_type == NodeType.START:
                if start_nodes >= 1:
                    raise ValidateException("工作流中只允许有1个开始节点")
                start_nodes += 1
            elif node_data.node_type == NodeType.END:
                if end_nodes >= 1:
                    raise ValidateException("工作流中只允许有1个结束节点")
                end_nodes += 1

            # 8.判断节点 id 是否唯一
            if node_data.id in node_data_dict:
                raise ValidateException("工作流节点id必须唯一，请核实后重试")

            # 9.判断节点 title 是否唯一
            if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                raise ValidateException("工作流节点title必须唯一，请核实后重试")

            node_data_dict[node_data.id] = node_data

        # 10.循环遍历 edges 数据
        edge_data_dict: dict = {}
        for edge in edges:
            if not isinstance(edge, dict):
                raise ValidateException("工作流边数据类型出错，请核实后重试")

            edge_data = BaseEdgeData(**edge)

            if edge_data.id in edge_data_dict:
                raise ValidateException("工作流边数据id必须唯一，请核实后重试")

            if (
                edge_data.source not in node_data_dict
                or edge_data.source_type != node_data_dict[edge_data.source].node_type
                or edge_data.target not in node_data_dict
                or edge_data.target_type != node_data_dict[edge_data.target].node_type
            ):
                raise ValidateException("工作流边起点/终点对应的节点不存在或类型错误，请核实后重试")

            # 11.校验边唯一性（source+target+source_handle_id）
            if any(
                (
                    item.source == edge_data.source
                    and item.target == edge_data.target
                    and item.source_handle_id == edge_data.source_handle_id
                )
                for item in edge_data_dict.values()
            ):
                raise ValidateException("工作流边数据不能重复添加")

            edge_data_dict[edge_data.id] = edge_data

        # 12.构建邻接表、逆邻接表、入度、出度
        adj_list = cls._build_adj_list(edge_data_dict.values())
        reverse_adj_list = cls._build_reverse_adj_list(edge_data_dict.values())
        in_degree, out_degree = cls._build_degrees(edge_data_dict.values())

        # 13.校验唯一开始/结束节点
        start_nodes_list = [nd for nd in node_data_dict.values() if in_degree[nd.id] == 0]
        end_nodes_list = [nd for nd in node_data_dict.values() if out_degree[nd.id] == 0]
        if (
            len(start_nodes_list) != 1
            or len(end_nodes_list) != 1
            or start_nodes_list[0].node_type != NodeType.START
            or end_nodes_list[0].node_type != NodeType.END
        ):
            raise ValidateException("工作流中有且只有一个开始/结束节点作为图结构的起点和终点")

        start_node_data = start_nodes_list[0]

        # 14.校验图连通性
        if not cls._is_connected(adj_list, start_node_data.id):
            raise ValidateException("工作流中存在不可到达节点，图不联通，请核实后重试")

        # 15.校验是否存在环路
        if cls._is_cycle(node_data_dict.values(), adj_list, in_degree):
            raise ValidateException("工作流中存在环路，请核实后重试")

        # 16.校验 inputs/outputs 数据引用
        cls._validate_inputs_ref(node_data_dict, reverse_adj_list)

        # 17.更新 values
        values["nodes"] = list(node_data_dict.values())
        values["edges"] = list(edge_data_dict.values())
        return values

    @classmethod
    def _is_connected(cls, adj_list: defaultdict, start_node_id: UUID) -> bool:
        """BFS 检查图是否连通"""
        visited = set()
        queue = deque([start_node_id])
        visited.add(start_node_id)
        while queue:
            node_id = queue.popleft()
            for neighbor in adj_list[node_id]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return len(visited) == len(adj_list)

    @classmethod
    def _is_cycle(cls, nodes: list, adj_list: defaultdict, in_degree: defaultdict) -> bool:
        """拓扑排序（Kahn 算法）检测环"""
        zero_in_degree_nodes = deque([node.id for node in nodes if in_degree[node.id] == 0])
        visited_count = 0
        while zero_in_degree_nodes:
            node_id = zero_in_degree_nodes.popleft()
            visited_count += 1
            for neighbor in adj_list[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    zero_in_degree_nodes.append(neighbor)
        return visited_count != len(nodes)

    @classmethod
    def _validate_inputs_ref(cls, node_data_dict: dict, reverse_adj_list: defaultdict) -> None:
        """校验输入数据引用是否正确"""
        for node_data in node_data_dict.values():
            predecessors = cls._get_predecessors(reverse_adj_list, node_data.id)

            if node_data.node_type != NodeType.START:
                variables: list[VariableEntity] = (
                    node_data.inputs if node_data.node_type != NodeType.END
                    else node_data.outputs
                )
                for variable in variables:
                    if variable.value.type == VariableValueType.REF:
                        if (
                            len(predecessors) <= 0
                            or variable.value.content.ref_node_id not in predecessors
                        ):
                            raise ValidateException(
                                f"工作流节点[{node_data.title}]引用数据出错，请核实后重试"
                            )
                        ref_node_data = node_data_dict.get(variable.value.content.ref_node_id)
                        ref_variables = (
                            ref_node_data.inputs if ref_node_data.node_type == NodeType.START
                            else ref_node_data.outputs
                        )
                        if not any(
                            ref_variable.name == variable.value.content.ref_var_name
                            for ref_variable in ref_variables
                        ):
                            raise ValidateException(
                                f"工作流节点[{node_data.title}]引用了不存在的节点变量，请核实后重试"
                            )

    @classmethod
    def _build_adj_list(cls, edges: list) -> defaultdict:
        adj_list = defaultdict(list)
        for edge in edges:
            adj_list[edge.source].append(edge.target)
        return adj_list

    @classmethod
    def _build_reverse_adj_list(cls, edges: list) -> defaultdict:
        reverse_adj_list = defaultdict(list)
        for edge in edges:
            reverse_adj_list[edge.target].append(edge.source)
        return reverse_adj_list

    @classmethod
    def _build_degrees(cls, edges: list) -> tuple:
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)
        for edge in edges:
            in_degree[edge.target] += 1
            out_degree[edge.source] += 1
        return in_degree, out_degree

    @classmethod
    def _get_predecessors(cls, reverse_adj_list: defaultdict, target_node_id: UUID) -> list:
        visited = set()
        predecessors = []

        def dfs(node_id):
            if node_id not in visited:
                visited.add(node_id)
                if node_id != target_node_id:
                    predecessors.append(node_id)
                for neighbor in reverse_adj_list[node_id]:
                    dfs(neighbor)

        dfs(target_node_id)
        return predecessors


class WorkflowState(TypedDict):
    """工作流图程序状态字典"""
    inputs: Annotated[dict, _process_dict]  # 工作流最初始输入（工具输入）
    outputs: Annotated[dict, _process_dict]  # 工作流最终输出结果（工具输出）
    node_results: Annotated[list[NodeResult], _process_node_results]  # 各节点运行结果
