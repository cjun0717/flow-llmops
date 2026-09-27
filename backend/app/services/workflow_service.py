#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流服务（async，迁移自 imooc workflow_service.py）。

提供工作流 CRUD、草稿图更新/读取、调试（SSE 流式）、发布/取消发布。
内置工具提供者管理器通过 deps 中的 lru_cache 单例访问器获取。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.workflow.entities.edge_entity import BaseEdgeData
from app.core.workflow.entities.node_entity import BaseNodeData, NodeStatus, NodeType
from app.core.workflow.entities.workflow_entity import WorkflowConfig
from app.core.workflow.nodes import (
    CodeNodeData,
    DatasetRetrievalNodeData,
    EndNodeData,
    HttpRequestNodeData,
    IterationNodeData,
    LLMNodeData,
    QuestionClassifierNodeData,
    StartNodeData,
    TemplateTransformNodeData,
    ToolNodeData,
)
from app.entities.workflow_entity import (
    DEFAULT_WORKFLOW_CONFIG,
    WorkflowResultStatus,
    WorkflowStatus,
)
from app.exceptions import (
    FailException,
    ForbiddenException,
    NotFoundException,
    ValidateException,
)
from app.lib.helper import convert_model_to_dict
from app.models.account import Account
from app.models.api_tool import ApiTool
from app.models.dataset import Dataset
from app.models.mcp_tool import McpTool
from app.models.workflow import Workflow, WorkflowResult
from app.schemas.response import HttpCode, PageData, page_data
from app.schemas.workflow import (
    GetWorkflowsWithPageReq,
    GetWorkflowsWithPageResp,
    GetWorkflowResp,
)


class WorkflowService:
    """工作流服务"""

    # ===== CRUD =====

    @staticmethod
    async def create_workflow(req, account: Account, db: AsyncSession) -> Workflow:
        """根据传递的请求信息创建工作流"""
        # 1.重名校验
        result = await db.execute(
            select(Workflow).where(
                Workflow.tool_call_name == req.tool_call_name.strip(),
                Workflow.account_id == account.id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ValidateException(f"在当前账号下已创建[{req.tool_call_name}]工作流，不支持重名")

        # 2.创建工作流
        workflow = Workflow(
            account_id=account.id,
            name=req.name,
            tool_call_name=req.tool_call_name.strip(),
            icon=req.icon,
            description=req.description,
            graph=DEFAULT_WORKFLOW_CONFIG["graph"],
            draft_graph=DEFAULT_WORKFLOW_CONFIG["draft_graph"],
            is_debug_passed=False,
            status=WorkflowStatus.DRAFT,
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)
        return workflow

    @staticmethod
    async def get_workflow(workflow_id: UUID, account: Account, db: AsyncSession) -> Workflow:
        """根据工作流 id 获取工作流基础信息并校验权限"""
        result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
        workflow = result.scalar_one_or_none()
        if not workflow:
            raise NotFoundException("该工作流不存在，请核实后重试")
        if workflow.account_id != account.id:
            raise ForbiddenException("当前账号无权限访问该应用，请核实后尝试")
        return workflow

    @staticmethod
    async def delete_workflow(workflow_id: UUID, account: Account, db: AsyncSession) -> Workflow:
        """删除指定的工作流"""
        workflow = await WorkflowService.get_workflow(workflow_id, account, db)
        await db.delete(workflow)
        await db.commit()
        return workflow

    @staticmethod
    async def update_workflow(workflow_id: UUID, account: Account, req, db: AsyncSession) -> Workflow:
        """更新工作流基础信息"""
        workflow = await WorkflowService.get_workflow(workflow_id, account, db)

        # 1.重名校验（排除自身）
        result = await db.execute(
            select(Workflow).where(
                Workflow.tool_call_name == req.tool_call_name.strip(),
                Workflow.account_id == account.id,
                Workflow.id != workflow.id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ValidateException(f"在当前账号下已创建[{req.tool_call_name}]工作流，不支持重名")

        # 2.更新
        workflow.name = req.name
        workflow.tool_call_name = req.tool_call_name.strip()
        workflow.icon = req.icon
        workflow.description = req.description
        await db.commit()
        return workflow

    @staticmethod
    async def get_workflows_with_page(
        req: GetWorkflowsWithPageReq, account: Account, db: AsyncSession
    ) -> PageData[GetWorkflowsWithPageResp]:
        """获取工作流分页列表数据"""
        filters = [Workflow.account_id == account.id]
        if req.search_word:
            filters.append(Workflow.name.ilike(f"%{req.search_word}%"))
        if req.status:
            filters.append(Workflow.status == req.status)

        # 总数
        count_result = await db.execute(
            select(func.count()).select_from(Workflow).where(*filters)
        )
        total_record = count_result.scalar() or 0

        # 分页数据
        result = await db.execute(
            select(Workflow)
            .where(*filters)
            .order_by(desc(Workflow.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        workflows = result.scalars().all()

        items = [GetWorkflowsWithPageResp.from_model(wf) for wf in workflows]
        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    # ===== 草稿图 =====

    @staticmethod
    async def update_draft_graph(
        workflow_id: UUID, draft_graph: dict, account: Account, db: AsyncSession
    ) -> Workflow:
        """更新工作流的草稿图配置"""
        workflow = await WorkflowService.get_workflow(workflow_id, account, db)

        # 1.校验草稿图
        validate_draft_graph = await WorkflowService._validate_graph(workflow_id, draft_graph, account, db)

        # 2.判断是否敏感变更
        is_debug_sensitive_changed = WorkflowService._is_debug_sensitive_graph_changed(
            workflow.draft_graph, validate_draft_graph
        )
        workflow.draft_graph = validate_draft_graph
        workflow.is_debug_passed = bool(workflow.is_debug_passed) and not is_debug_sensitive_changed
        await db.commit()
        return workflow

    @staticmethod
    async def get_draft_graph(
        workflow_id: UUID, account: Account, db: AsyncSession, base_url: str
    ) -> dict:
        """获取工作流的草稿配置信息（为工具/知识库/迭代节点附加 meta）"""
        workflow = await WorkflowService.get_workflow(workflow_id, account, db)

        draft_graph = workflow.draft_graph
        validate_draft_graph = await WorkflowService._validate_graph(workflow_id, draft_graph, account, db)

        from app.deps import get_builtin_provider_manager
        builtin_provider_manager = get_builtin_provider_manager()

        for node in validate_draft_graph["nodes"]:
            if node.get("node_type") == NodeType.TOOL:
                await WorkflowService._fill_tool_node_meta(
                    node, account, db, builtin_provider_manager, base_url
                )
            elif node.get("node_type") == NodeType.DATASET_RETRIEVAL:
                await WorkflowService._fill_dataset_node_meta(node, account, db)
            elif node.get("node_type") == NodeType.ITERATION:
                await WorkflowService._fill_iteration_node_meta(node, account, db)

        return validate_draft_graph

    @staticmethod
    async def _fill_tool_node_meta(node, account, db, builtin_provider_manager, base_url):
        """为工具节点附加展示元数据"""
        if node.get("tool_type") == "builtin_tool":
            provider = builtin_provider_manager.get_provider(node.get("provider_id"))
            if not provider:
                return
            tool_entity = provider.get_tool_entity(node.get("tool_id"))
            if not tool_entity:
                return

            # 判断 params 是否一致，不一致则重置为默认值
            param_keys = set([param.name for param in tool_entity.params])
            params = node.get("params")
            if set(params.keys()) - param_keys:
                params = {
                    param.name: param.default
                    for param in tool_entity.params
                    if param.default is not None
                }

            provider_entity = provider.provider_entity
            node["meta"] = {
                "type": "builtin_tool",
                "provider": {
                    "id": provider_entity.name,
                    "name": provider_entity.name,
                    "label": provider_entity.label,
                    "icon": f"{base_url}builtin-tools/{provider_entity.name}/icon",
                    "description": provider_entity.description,
                },
                "tool": {
                    "id": tool_entity.name,
                    "name": tool_entity.name,
                    "label": tool_entity.label,
                    "description": tool_entity.description,
                    "params": params,
                },
            }
        elif node.get("tool_type") == "api_tool":
            result = await db.execute(
                select(ApiTool).where(
                    ApiTool.provider_id == UUID(node.get("provider_id")),
                    ApiTool.name == node.get("tool_id"),
                    ApiTool.account_id == account.id,
                )
            )
            tool_record = result.scalar_one_or_none()
            if not tool_record:
                return
            from app.models.api_tool import ApiToolProvider
            prov_result = await db.execute(
                select(ApiToolProvider).where(ApiToolProvider.id == tool_record.provider_id)
            )
            provider = prov_result.scalar_one()
            node["meta"] = {
                "type": "api_tool",
                "provider": {
                    "id": str(provider.id),
                    "name": provider.name,
                    "label": provider.name,
                    "icon": provider.icon,
                    "description": provider.description,
                },
                "tool": {
                    "id": str(tool_record.id),
                    "name": tool_record.name,
                    "label": tool_record.name,
                    "description": tool_record.description,
                    "params": {},
                },
            }
        elif node.get("tool_type") == "mcp_tool":
            result = await db.execute(
                select(McpTool).where(
                    McpTool.provider_id == UUID(node.get("provider_id")),
                    McpTool.name == node.get("tool_id"),
                    McpTool.account_id == account.id,
                )
            )
            tool_record = result.scalar_one_or_none()
            if not tool_record:
                return
            from app.models.mcp_tool import McpToolProvider
            prov_result = await db.execute(
                select(McpToolProvider).where(McpToolProvider.id == tool_record.provider_id)
            )
            provider = prov_result.scalar_one()
            node["meta"] = {
                "type": "mcp_tool",
                "provider": {
                    "id": str(provider.id),
                    "name": provider.name,
                    "label": provider.name,
                    "icon": "",
                    "description": provider.description,
                },
                "tool": {
                    "id": str(tool_record.id),
                    "name": tool_record.name,
                    "label": tool_record.name,
                    "description": tool_record.description,
                    "params": {},
                },
            }
        else:
            node["meta"] = {
                "type": "api_tool",
                "provider": {"id": "", "name": "", "label": "", "icon": "", "description": ""},
                "tool": {"id": "", "name": "", "label": "", "description": "", "params": {}},
            }

    @staticmethod
    async def _fill_dataset_node_meta(node, account, db):
        """为知识库检索节点附加展示元数据"""
        result = await db.execute(
            select(Dataset).where(
                Dataset.id.in_([UUID(did) for did in node.get("dataset_ids", [])]),
                Dataset.account_id == account.id,
            )
        )
        datasets = result.scalars().all()
        datasets = datasets[:5]
        node["dataset_ids"] = [str(dataset.id) for dataset in datasets]
        node["meta"] = {
            "datasets": [{
                "id": str(dataset.id),
                "name": dataset.name,
                "icon": dataset.icon,
                "description": dataset.description,
            } for dataset in datasets]
        }

    @staticmethod
    async def _fill_iteration_node_meta(node, account, db):
        """为迭代节点附加展示元数据"""
        result = await db.execute(
            select(Workflow).where(
                Workflow.id.in_([UUID(wid) for wid in node.get("workflow_ids", [])]),
                Workflow.account_id == account.id,
                Workflow.status == WorkflowStatus.PUBLISHED,
            )
        )
        workflows = result.scalars().all()
        workflows = workflows[:1]
        node["workflow_ids"] = [str(workflow.id) for workflow in workflows]
        node["meta"] = {
            "workflows": [{
                "id": str(workflow.id),
                "name": workflow.name,
                "icon": workflow.icon,
                "description": workflow.description,
            } for workflow in workflows]
        }

    # ===== 调试（SSE 流式） =====

    @staticmethod
    async def debug_workflow(
        workflow_id: UUID, inputs: dict, account: Account, db: AsyncSession
    ) -> AsyncGenerator[str, None]:
        """调试指定的工作流，流式事件输出"""
        try:
            # 1.获取工作流并校验权限
            workflow = await WorkflowService.get_workflow(workflow_id, account, db)

            # 2.创建工作流运行结果记录
            workflow_result = WorkflowResult(
                app_id=None,
                account_id=account.id,
                workflow_id=workflow.id,
                graph=workflow.draft_graph,
                state=[],
                latency=0,
                status=WorkflowResultStatus.RUNNING,
            )
            db.add(workflow_result)
            await db.flush()

            workflow_id_str = workflow.id
            draft_graph = workflow.draft_graph
            tool_call_name = workflow.tool_call_name
            description = workflow.description
            account_id = account.id
            result_id = workflow_result.id

            # 3.同步生成器：在子线程中构建工作流工具并流式输出
            def run_stream():
                from app.core.workflow.workflow import Workflow as WorkflowTool
                workflow_tool = WorkflowTool(workflow_config=WorkflowConfig(
                    account_id=account_id,
                    name=tool_call_name,
                    description=description,
                    nodes=draft_graph.get("nodes", []),
                    edges=draft_graph.get("edges", []),
                ))
                for chunk in workflow_tool.stream(inputs):
                    yield chunk

            sync_gen = run_stream()
            loop = asyncio.get_event_loop()
            sentinel = object()

            def _next_or_none(it):
                try:
                    return next(it)
                except StopIteration:
                    return sentinel

            node_results: list = []
            start_at = time.perf_counter()
            try:
                while True:
                    chunk = await loop.run_in_executor(None, _next_or_none, sync_gen)
                    if chunk is sentinel:
                        break

                    first_key = next(iter(chunk))
                    # 虚拟节点无 node_results，跳过
                    if len(chunk[first_key]["node_results"]) == 0:
                        continue
                    node_result = chunk[first_key]["node_results"][0]
                    if node_result.status == NodeStatus.FAILED and not node_result.error:
                        node_result.error = f"工作流节点[{node_result.node_data.title}]运行失败"
                    node_result_dict = convert_model_to_dict(node_result)
                    node_results.append(node_result_dict)

                    data = {
                        "id": str(uuid.uuid4()),
                        **node_result_dict,
                    }
                    yield f"event: workflow\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

                    if node_result.status == NodeStatus.FAILED:
                        error = node_result.error or f"工作流节点[{node_result.node_data.title}]运行失败"
                        raise FailException(error)

                # 4.流式输出完毕，更新结果为成功
                await WorkflowService._update_workflow_result(
                    result_id, db,
                    status=WorkflowResultStatus.SUCCEEDED,
                    state=node_results,
                    latency=(time.perf_counter() - start_at),
                )
                await WorkflowService._update_workflow_debug_status(workflow_id_str, db, True)
            except Exception as e:
                logging.exception("执行工作流发生错误, 错误信息: %s", e)
                await WorkflowService._update_workflow_result(
                    result_id, db,
                    status=WorkflowResultStatus.FAILED,
                    state=node_results,
                    latency=(time.perf_counter() - start_at),
                )
                await WorkflowService._update_workflow_debug_status(workflow_id_str, db, False)
                raise
        except Exception as error:
            code = getattr(error, "code", HttpCode.FAIL)
            message = getattr(error, "message", str(error))
            data = getattr(error, "data", {}) or {}
            yield "event: error\ndata:" + json.dumps({
                "code": code.value if hasattr(code, "value") else str(code),
                "message": message,
                "data": data,
            }, ensure_ascii=False) + "\n\n"

    @staticmethod
    async def _update_workflow_result(
        result_id: UUID, db: AsyncSession, *, status: str, state: list, latency: float
    ) -> None:
        """更新工作流运行结果记录"""
        result = await db.execute(select(WorkflowResult).where(WorkflowResult.id == result_id))
        workflow_result = result.scalar_one_or_none()
        if workflow_result:
            workflow_result.status = status
            workflow_result.state = state
            workflow_result.latency = latency
            await db.commit()

    @staticmethod
    async def _update_workflow_debug_status(
        workflow_id: UUID, db: AsyncSession, is_debug_passed: bool
    ) -> None:
        """更新工作流调试通过状态"""
        result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
        workflow_record = result.scalar_one_or_none()
        if workflow_record:
            workflow_record.is_debug_passed = is_debug_passed
            await db.commit()

    # ===== 发布 =====

    @staticmethod
    async def publish_workflow(workflow_id: UUID, account: Account, db: AsyncSession) -> Workflow:
        """发布指定的工作流"""
        workflow = await WorkflowService.get_workflow(workflow_id, account, db)

        # 1.校验是否调试通过
        if workflow.is_debug_passed is False:
            raise FailException("该工作流未调试通过，请调试通过后发布")

        # 2.使用 WorkflowConfig 二次校验
        try:
            WorkflowConfig(
                account_id=account.id,
                name=workflow.tool_call_name,
                description=workflow.description,
                nodes=workflow.draft_graph.get("nodes", []),
                edges=workflow.draft_graph.get("edges", []),
            )
        except Exception:
            workflow.is_debug_passed = False
            await db.commit()
            raise ValidateException("工作流配置校验失败，请核实后重试")

        # 3.更新发布状态
        workflow.graph = workflow.draft_graph
        workflow.status = WorkflowStatus.PUBLISHED
        workflow.is_debug_passed = False
        await db.commit()
        return workflow

    @staticmethod
    async def cancel_publish_workflow(
        workflow_id: UUID, account: Account, db: AsyncSession
    ) -> Workflow:
        """取消发布指定的工作流"""
        workflow = await WorkflowService.get_workflow(workflow_id, account, db)

        if workflow.status != WorkflowStatus.PUBLISHED:
            raise FailException("该工作流未发布无法取消发布")

        workflow.graph = {}
        workflow.status = WorkflowStatus.DRAFT
        workflow.is_debug_passed = False
        await db.commit()
        return workflow

    # ===== 草稿图归一化与校验 =====

    @classmethod
    def _is_debug_sensitive_graph_changed(
        cls,
        previous_graph: dict,
        next_graph: dict,
    ) -> bool:
        """判断草稿图中会影响运行结果的配置是否发生变化"""
        return cls._normalize_graph_for_debug(previous_graph) != cls._normalize_graph_for_debug(next_graph)

    @classmethod
    def _normalize_graph_for_debug(cls, graph: dict) -> dict:
        """归一化工作流图，忽略不影响执行结果的节点坐标和展示元数据"""

        def normalize_value(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: normalize_value(value[key]) for key in sorted(value) if key != "meta"}
            if isinstance(value, list):
                return [normalize_value(item) for item in value]
            return str(value) if isinstance(value, UUID) else value

        def normalize_node(node: dict) -> dict:
            normalized_node = dict(node)
            normalized_node.pop("position", None)
            normalized_node.pop("meta", None)
            return normalize_value(normalized_node)

        nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
        edges = graph.get("edges", []) if isinstance(graph, dict) else []

        return {
            "nodes": sorted(
                [normalize_node(node) for node in nodes if isinstance(node, dict)],
                key=lambda node: str(node.get("id", "")),
            ),
            "edges": sorted(
                [normalize_value(edge) for edge in edges if isinstance(edge, dict)],
                key=lambda edge: (
                    str(edge.get("source", "")),
                    str(edge.get("target", "")),
                    str(edge.get("source_handle_id", "")),
                    str(edge.get("id", "")),
                ),
            ),
        }

    @staticmethod
    async def _validate_graph(
        workflow_id: UUID, graph: dict, account: Account, db: AsyncSession
    ) -> dict:
        """校验传递的 graph 信息（宽松校验，草稿不需要校验节点与边的关系）"""
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        # 1.构建节点类型与节点数据类映射
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

        # 2.循环校验 nodes
        node_data_dict: dict = {}
        start_nodes = 0
        end_nodes = 0
        for node in nodes:
            try:
                if not isinstance(node, dict):
                    raise ValidateException("工作流节点数据类型出错，请核实后重试")

                node_type = node.get("node_type", "")
                node_data_cls = node_data_classes.get(node_type, None)
                if node_data_cls is None:
                    raise ValidateException("工作流节点类型出错，请核实后重试")

                node_data = node_data_cls(**node)

                if node_data.id in node_data_dict:
                    raise ValidateException("工作流节点id必须唯一，请核实后重试")

                if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                    raise ValidateException("工作流节点title必须唯一，请核实后重试")

                # 3.特殊节点处理
                if node_data.node_type == NodeType.START:
                    if start_nodes >= 1:
                        raise ValidateException("工作流中只允许有1个开始节点")
                    start_nodes += 1
                elif node_data.node_type == NodeType.END:
                    if end_nodes >= 1:
                        raise ValidateException("工作流中只允许有1个结束节点")
                    end_nodes += 1
                elif node_data.node_type == NodeType.DATASET_RETRIEVAL:
                    # 剔除不属于当前账户的知识库
                    result = await db.execute(
                        select(Dataset).where(
                            Dataset.id.in_(node_data.dataset_ids[:5]),
                            Dataset.account_id == account.id,
                        )
                    )
                    datasets = result.scalars().all()
                    node_data.dataset_ids = [dataset.id for dataset in datasets]
                elif node_data.node_type == NodeType.ITERATION:
                    # 剔除不属于当前账户且未发布的工作流，且不能内嵌本身
                    result = await db.execute(
                        select(Workflow).where(
                            Workflow.id.in_(node_data.workflow_ids[:1]),
                            Workflow.account_id == account.id,
                            Workflow.status == WorkflowStatus.PUBLISHED,
                        )
                    )
                    workflows = result.scalars().all()
                    node_data.workflow_ids = [
                        workflow.id for workflow in workflows if workflow.id != workflow_id
                    ]

                node_data_dict[node_data.id] = node_data
            except Exception:
                continue

        # 4.循环校验 edges
        edge_data_dict: dict = {}
        for edge in edges:
            try:
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
            except Exception:
                continue

        return {
            "nodes": [convert_model_to_dict(node_data) for node_data in node_data_dict.values()],
            "edges": [convert_model_to_dict(edge_data) for edge_data in edge_data_dict.values()],
        }
