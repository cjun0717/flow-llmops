#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MCP 插件服务（async，迁移自 imooc mcp_tool_service.py）。"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from langchain_core.tools import BaseTool
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tools.mcp_tools.providers import McpProviderManager
from app.exceptions import NotFoundException, ValidateException
from app.models.account import Account
from app.models.mcp_tool import McpTool, McpToolProvider
from app.schemas.mcp_tool import (
    CreateMcpToolReq,
    GetMcpToolProvidersWithPageReq,
    GetMcpToolProvidersWithPageResp,
    GetMcpToolProviderResp,
    GetMcpToolResp,
    UpdateMcpToolProviderReq,
)
from app.schemas.response import PageData, page_data


SUPPORTED_TRANSPORTS = {"http", "streamable_http", "streamable-http", "streamhttp"}
UNSUPPORTED_TRANSPORTS = {"stdio", "sse", "websocket"}


class McpToolService:
    """MCP 插件服务"""

    def __init__(self, mcp_provider_manager: McpProviderManager) -> None:
        self.mcp_provider_manager = mcp_provider_manager

    @staticmethod
    async def _get_provider_owned(
        provider_id: UUID, account: Account, db: AsyncSession
    ) -> McpToolProvider:
        result = await db.execute(
            select(McpToolProvider).where(McpToolProvider.id == provider_id)
        )
        provider = result.scalar_one_or_none()
        if provider is None or provider.account_id != account.id:
            raise NotFoundException("该MCP工具提供者不存在")
        return provider

    @staticmethod
    async def _list_tools(provider_id: UUID, db: AsyncSession) -> list[McpTool]:
        result = await db.execute(select(McpTool).where(McpTool.provider_id == provider_id))
        return list(result.scalars().all())

    def validate_mcp_schema(self, mcp_schema: str) -> list[dict[str, Any]]:
        """校验 MCP 配置并返回可用工具预览"""
        servers = self.parse_mcp_schema(mcp_schema)
        previews = []
        for server in servers:
            tools = self._load_remote_tools(server)
            previews.append({**server, "tools": tools})
        return previews

    async def create_mcp_tools(
        self, req: CreateMcpToolReq, account: Account, db: AsyncSession
    ) -> None:
        """根据传递的请求批量创建 MCP 插件"""
        servers = self.parse_mcp_schema(req.mcp_schema)
        server_names = [server["name"] for server in servers]
        if len(server_names) != len(set(server_names)):
            raise ValidateException("MCP服务器名称存在重复")

        exists_count_result = await db.execute(
            select(func.count())
            .select_from(McpToolProvider)
            .where(
                McpToolProvider.account_id == account.id,
                McpToolProvider.name.in_(server_names),
            )
        )
        if (exists_count_result.scalar() or 0) > 0:
            raise ValidateException("当前账号下已存在同名MCP服务器")

        server_tools: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        for server in servers:
            tools = self._load_remote_tools(server)
            server_tools.append((server, tools))

        for server, tools in server_tools:
            provider = McpToolProvider(
                account_id=account.id,
                name=server["name"],
                description=server["description"],
                transport=server["config"]["transport"],
                url=server["config"]["url"],
                headers=server["config"]["headers"],
                config=server["config"],
                mcp_schema=server["mcp_schema"],
            )
            db.add(provider)
            await db.flush()

            for tool in tools:
                db.add(
                    McpTool(
                        account_id=account.id,
                        provider_id=provider.id,
                        name=tool["name"],
                        description=tool["description"],
                        input_schema=tool["input_schema"],
                        tool_metadata=tool["metadata"],
                    )
                )
        await db.commit()

    async def update_mcp_tool_provider(
        self,
        provider_id: UUID,
        req: UpdateMcpToolProviderReq,
        account: Account,
        db: AsyncSession,
    ) -> None:
        """更新 MCP 工具提供者信息并重新同步工具列表"""
        provider = await McpToolService._get_provider_owned(provider_id, account, db)
        servers = self.parse_mcp_schema(req.mcp_schema)
        if len(servers) != 1:
            raise ValidateException("更新单个MCP服务器时只允许传递一个mcpServers配置")

        server = servers[0]
        check_result = await db.execute(
            select(McpToolProvider).where(
                McpToolProvider.account_id == account.id,
                McpToolProvider.name == server["name"],
                McpToolProvider.id != provider.id,
            )
        )
        if check_result.scalar_one_or_none() is not None:
            raise ValidateException("当前账号下已存在同名MCP服务器")

        tools = self._load_remote_tools(server)

        await db.execute(
            delete(McpTool).where(
                McpTool.provider_id == provider.id,
                McpTool.account_id == account.id,
            )
        )

        provider.name = server["name"]
        provider.description = server["description"]
        provider.transport = server["config"]["transport"]
        provider.url = server["config"]["url"]
        provider.headers = server["config"]["headers"]
        provider.config = server["config"]
        provider.mcp_schema = server["mcp_schema"]

        for tool in tools:
            db.add(
                McpTool(
                    account_id=account.id,
                    provider_id=provider.id,
                    name=tool["name"],
                    description=tool["description"],
                    input_schema=tool["input_schema"],
                    tool_metadata=tool["metadata"],
                )
            )
        await db.commit()

    @staticmethod
    async def get_mcp_tool_providers_with_page(
        req: GetMcpToolProvidersWithPageReq, account: Account, db: AsyncSession
    ) -> PageData[GetMcpToolProvidersWithPageResp]:
        """获取 MCP 工具服务提供者分页列表数据"""
        filters = [McpToolProvider.account_id == account.id]
        if req.search_word:
            filters.append(McpToolProvider.name.ilike(f"%{req.search_word}%"))

        count_result = await db.execute(
            select(func.count()).select_from(McpToolProvider).where(*filters)
        )
        total_record = count_result.scalar() or 0

        result = await db.execute(
            select(McpToolProvider)
            .where(*filters)
            .order_by(desc(McpToolProvider.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        providers = result.scalars().all()

        items: list[GetMcpToolProvidersWithPageResp] = []
        for provider in providers:
            tools = await McpToolService._list_tools(provider.id, db)
            items.append(GetMcpToolProvidersWithPageResp.from_model(provider, tools))

        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @staticmethod
    async def get_mcp_tool(
        provider_id: UUID, tool_name: str, account: Account, db: AsyncSession
    ) -> GetMcpToolResp:
        """根据 provider_id 和 tool_name 获取 MCP 工具详情"""
        result = await db.execute(
            select(McpTool).where(
                McpTool.provider_id == provider_id,
                McpTool.name == tool_name,
            )
        )
        tool = result.scalar_one_or_none()
        if tool is None or tool.account_id != account.id:
            raise NotFoundException("该MCP工具不存在")

        prov_result = await db.execute(
            select(McpToolProvider).where(McpToolProvider.id == provider_id)
        )
        tool.provider = prov_result.scalar_one()  # type: ignore[attr-defined]
        return GetMcpToolResp.from_model(tool)

    @staticmethod
    async def get_mcp_tool_provider(
        provider_id: UUID, account: Account, db: AsyncSession
    ) -> GetMcpToolProviderResp:
        """根据 provider_id 获取 MCP 工具提供者"""
        provider = await McpToolService._get_provider_owned(provider_id, account, db)
        tools = await McpToolService._list_tools(provider.id, db)
        return GetMcpToolProviderResp.from_model(provider, tools)

    @staticmethod
    async def delete_mcp_tool_provider(
        provider_id: UUID, account: Account, db: AsyncSession
    ) -> None:
        """删除 MCP 工具提供者及其工具"""
        provider = await McpToolService._get_provider_owned(provider_id, account, db)
        await db.execute(
            delete(McpTool).where(
                McpTool.provider_id == provider_id,
                McpTool.account_id == account.id,
            )
        )
        await db.delete(provider)
        await db.commit()

    # ===== MCP schema 解析与远程工具加载 =====

    @classmethod
    def parse_mcp_schema(cls, mcp_schema_str: str) -> list[dict[str, Any]]:
        """解析并校验 MCP JSON 配置"""
        try:
            data = json.loads(mcp_schema_str.strip())
            if not isinstance(data, dict):
                raise ValueError("MCP schema must be a JSON object")
        except Exception as e:
            raise ValidateException("传递数据必须是符合MCP配置规范的JSON字符串") from e

        servers = data.get("mcpServers")
        if not isinstance(servers, dict) or len(servers) <= 0:
            raise ValidateException("MCP配置必须包含非空的mcpServers对象")

        normalized_servers: list[dict[str, Any]] = []
        for server_name, server_config in servers.items():
            if not isinstance(server_name, str) or not server_name.strip():
                raise ValidateException("MCP服务器名称不能为空")
            if not isinstance(server_config, dict):
                raise ValidateException(f"MCP服务器{server_name}配置必须是对象")
            if server_config.get("disabled") is True:
                continue

            cls._reject_unsupported_transport(server_name, server_config)
            transport = cls._normalize_transport(server_name, server_config.get("transport", "http"))
            url = cls._validate_url(server_name, server_config.get("url"))
            headers = cls._validate_headers(server_name, server_config.get("headers", {}) or {})
            description = server_config.get("description")
            if not isinstance(description, str) or not description.strip():
                description = f"MCP Streamable HTTP server: {url}"

            config = {
                "transport": transport,
                "url": url,
                "headers": headers,
            }
            normalized_servers.append(
                {
                    "name": server_name.strip(),
                    "description": description,
                    "config": config,
                    "mcp_schema": json.dumps(
                        {
                            "mcpServers": {
                                server_name.strip(): {**server_config, **config}
                            }
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                }
            )

        if len(normalized_servers) <= 0:
            raise ValidateException("MCP配置中没有启用的服务器")

        return normalized_servers

    @staticmethod
    def _reject_unsupported_transport(server_name: str, server_config: dict[str, Any]) -> None:
        transport = server_config.get("transport")
        if transport in UNSUPPORTED_TRANSPORTS or any(
            key in server_config for key in ["command", "args", "env", "cwd"]
        ):
            raise ValidateException(
                f"当前仅支持Streamable HTTP MCP服务器，不支持本地stdio MCP：{server_name}"
            )

    @staticmethod
    def _normalize_transport(server_name: str, transport: Any) -> str:
        if not isinstance(transport, str):
            raise ValidateException(f"MCP服务器{server_name}的transport必须是字符串")
        transport = transport.strip()
        if transport not in SUPPORTED_TRANSPORTS:
            raise ValidateException(
                f"当前仅支持Streamable HTTP MCP服务器，不支持transport={transport}"
            )
        return "http"

    @staticmethod
    def _validate_url(server_name: str, url: Any) -> str:
        if not isinstance(url, str) or not url.strip():
            raise ValidateException(f"MCP服务器{server_name}的url不能为空")
        url = McpProviderManager.normalize_url(url)
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"] or not parsed.netloc:
            raise ValidateException(f"MCP服务器{server_name}的url必须是HTTP/HTTPS地址")
        return url

    @staticmethod
    def _validate_headers(server_name: str, headers: Any) -> dict[str, str]:
        if not isinstance(headers, dict):
            raise ValidateException(f"MCP服务器{server_name}的headers必须是对象")
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValidateException(f"MCP服务器{server_name}的headers键和值必须都是字符串")
        return headers

    def _load_remote_tools(self, server: dict[str, Any]) -> list[dict[str, Any]]:
        """连接远程 MCP 服务器并加载工具"""
        try:
            connection = self.mcp_provider_manager.build_connection(
                server["config"]["url"],
                server["config"]["headers"],
            )
            tools = self.mcp_provider_manager.load_tools(
                server["name"],
                connection,
                tool_name_prefix=False,
            )
            self._probe_known_credentials(server, tools)
        except Exception as e:
            raise ValidateException(
                f"MCP服务器{server['name']}连接失败或工具列表读取失败: {str(e)}"
            ) from e

        if len(tools) <= 0:
            raise ValidateException(f"MCP服务器{server['name']}没有返回可用工具")

        return [self._transform_langchain_tool(tool) for tool in tools]

    def _probe_known_credentials(self, server: dict[str, Any], tools: list[BaseTool]) -> None:
        """对部分会匿名返回工具列表的 MCP 服务做轻量凭证探测"""
        parsed = urlparse(server["config"]["url"])
        server_name = server["name"].lower()
        if parsed.netloc != "mcp.amap.com" and "amap" not in server_name:
            return

        probe_args_by_tool = {
            "maps_weather": {"city": "北京"},
            "maps_geo": {"address": "北京市"},
        }
        tool_map = {tool.name: tool for tool in tools}
        for tool_name, tool_args in probe_args_by_tool.items():
            tool = tool_map.get(tool_name)
            if tool is None:
                continue
            self.mcp_provider_manager.invoke_loaded_tool(tool, tool_args)
            return

    @staticmethod
    def _transform_langchain_tool(tool: BaseTool) -> dict[str, Any]:
        """将 LangChain 工具转换为可落库的 MCP 工具信息"""
        return {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": McpToolService._dump_args_schema(tool.args_schema),
            "metadata": McpToolService._jsonable(tool.metadata or {}),
        }

    @staticmethod
    def _dump_args_schema(args_schema: Any) -> dict[str, Any]:
        if isinstance(args_schema, dict):
            return McpToolService._jsonable(args_schema)
        if isinstance(args_schema, type) and issubclass(args_schema, PydanticBaseModel):
            return args_schema.model_json_schema()
        if isinstance(args_schema, PydanticBaseModel):
            return args_schema.model_dump(mode="json")
        return {}

    @staticmethod
    def _jsonable(value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
