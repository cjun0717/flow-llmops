#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""扩展插件节点（迁移自 imooc tool_node.py）。

适配 FastAPI：内置/API/MCP 工具提供者管理器通过 deps 中的 lru_cache 单例访问器获取；
API/MCP 工具的数据库查询在子线程中用 asyncio.run + 全新 AsyncSession 执行。
"""
from __future__ import annotations

import json
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
from app.exceptions import FailException, NotFoundException
from .tool_entity import ToolNodeData


class ToolNode(BaseNode):
    """扩展插件节点"""
    node_data: ToolNodeData
    _tool: BaseTool = PrivateAttr(None)

    def __init__(self, *args: Any, **kwargs: Any):
        """构造函数，完成对内置/API/MCP 工具的初始化"""
        super().__init__(*args, **kwargs)

        # 1.内置工具
        if self.node_data.tool_type == "builtin_tool":
            from app.deps import get_builtin_provider_manager
            builtin_provider_manager = get_builtin_provider_manager()
            _tool = builtin_provider_manager.get_tool(self.node_data.provider_id, self.node_data.tool_id)
            if not _tool:
                raise NotFoundException("该内置插件扩展不存在，请核实后重试")
            self._tool = _tool(**self.node_data.params)

        # 2.API 工具
        elif self.node_data.tool_type == "api_tool":
            self._tool = self._build_api_tool()

        # 3.MCP 工具
        elif self.node_data.tool_type == "mcp_tool":
            self._tool = self._build_mcp_tool()
        else:
            raise NotFoundException("该扩展插件不存在，请核实后重试")

    def _build_api_tool(self) -> BaseTool:
        """查询数据库获取 API 工具并构建 LangChain 工具"""
        from app.db import AsyncSessionLocal
        from app.models.api_tool import ApiTool, ApiToolProvider
        from app.core.tools.api_tools.entities import ToolEntity
        from app.core.tools.api_tools.providers import ApiProviderManager
        from sqlalchemy import select

        provider_id_str = self.node_data.provider_id
        tool_id = self.node_data.tool_id

        async def _query():
            async with AsyncSessionLocal() as db:
                tool_result = await db.execute(
                    select(ApiTool).where(
                        ApiTool.provider_id == UUID(provider_id_str),
                        ApiTool.name == tool_id,
                    )
                )
                api_tool = tool_result.scalar_one_or_none()
                if not api_tool:
                    raise NotFoundException("该API扩展插件不存在，请核实重试")
                prov_result = await db.execute(
                    select(ApiToolProvider).where(ApiToolProvider.id == api_tool.provider_id)
                )
                provider = prov_result.scalar_one()
                return api_tool, provider

        api_tool, provider = self._run_sync(_query())

        api_provider_manager = ApiProviderManager()
        return api_provider_manager.get_tool(ToolEntity(
            id=str(api_tool.id),
            name=api_tool.name,
            url=api_tool.url,
            method=api_tool.method,
            description=api_tool.description,
            headers=provider.headers,
            parameters=api_tool.parameters,
        ))

    def _build_mcp_tool(self) -> BaseTool:
        """查询数据库获取 MCP 工具并构建 LangChain 工具"""
        from app.db import AsyncSessionLocal
        from app.models.mcp_tool import McpTool, McpToolProvider
        from app.core.tools.mcp_tools.entities import McpToolEntity
        from app.core.tools.mcp_tools.providers import McpProviderManager
        from sqlalchemy import select

        provider_id_str = self.node_data.provider_id
        tool_id = self.node_data.tool_id

        async def _query():
            async with AsyncSessionLocal() as db:
                tool_result = await db.execute(
                    select(McpTool).where(
                        McpTool.provider_id == UUID(provider_id_str),
                        McpTool.name == tool_id,
                    )
                )
                mcp_tool = tool_result.scalar_one_or_none()
                if not mcp_tool:
                    raise NotFoundException("该MCP扩展插件不存在，请核实后重试")
                prov_result = await db.execute(
                    select(McpToolProvider).where(McpToolProvider.id == mcp_tool.provider_id)
                )
                provider = prov_result.scalar_one()
                return mcp_tool, provider

        mcp_tool, provider = self._run_sync(_query())

        mcp_provider_manager = McpProviderManager()
        return mcp_provider_manager.get_tool(McpToolEntity(
            provider_id=str(provider.id),
            name=mcp_tool.name,
            description=mcp_tool.description,
            url=provider.url,
            headers=provider.headers,
            input_schema=mcp_tool.input_schema,
            metadata=mcp_tool.tool_metadata,
        ))

    @staticmethod
    def _run_sync(coro):
        from app.core.workflow.utils.db_helper import run_sync
        return run_sync(coro)

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """根据传递的信息调用预设的插件，涵盖内置/API/MCP 插件"""
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        try:
            result = self._tool.invoke(inputs_dict)
        except Exception as e:
            error_message = str(e).strip()[:300]
            if error_message:
                raise FailException(f"扩展插件执行失败：{error_message}")
            raise FailException("扩展插件执行失败，请稍后尝试")

        if not isinstance(result, str):
            result = json.dumps(result, ensure_ascii=False)

        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = result
        else:
            outputs["text"] = result

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
