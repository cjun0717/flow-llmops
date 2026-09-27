#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""自定义 API 插件服务（async，迁移自 imooc api_tool_service.py）。"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tools.api_tools.entities import OpenAPISchema
from app.exceptions import NotFoundException, ValidateException
from app.models.account import Account
from app.models.api_tool import ApiTool, ApiToolProvider
from app.schemas.api_tool import (
    CreateApiToolReq,
    GetApiToolProvidersWithPageReq,
    GetApiToolProvidersWithPageResp,
    GetApiToolProviderResp,
    GetApiToolResp,
    UpdateApiToolProviderReq,
)
from app.schemas.response import PageData, page_data


class ApiToolService:
    """自定义 API 插件服务"""

    @staticmethod
    async def _get_provider_owned(
        provider_id: UUID, account: Account, db: AsyncSession
    ) -> ApiToolProvider:
        result = await db.execute(select(ApiToolProvider).where(ApiToolProvider.id == provider_id))
        provider = result.scalar_one_or_none()
        if provider is None or provider.account_id != account.id:
            raise NotFoundException("该工具提供者不存在")
        return provider

    @staticmethod
    async def _list_tools(provider_id: UUID, db: AsyncSession) -> list[ApiTool]:
        result = await db.execute(
            select(ApiTool).where(ApiTool.provider_id == provider_id)
        )
        return list(result.scalars().all())

    @staticmethod
    def parse_openapi_schema(openapi_schema_str: str) -> OpenAPISchema:
        """解析传递的 openapi_schema 字符串，如果出错则抛出错误"""
        try:
            data = json.loads(openapi_schema_str.strip())
            if not isinstance(data, dict):
                raise ValueError("OpenAPI schema must be a JSON object")
        except Exception as e:
            raise ValidateException("传递数据必须符合OpenAPI规范的JSON字符串") from e
        return OpenAPISchema(**data)

    @staticmethod
    async def create_api_tool(req: CreateApiToolReq, account: Account, db: AsyncSession) -> None:
        """根据传递的请求创建自定义 API 工具"""
        openapi_schema = ApiToolService.parse_openapi_schema(req.openapi_schema)

        # 同名检测
        result = await db.execute(
            select(ApiToolProvider).where(
                ApiToolProvider.account_id == account.id,
                ApiToolProvider.name == req.name,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ValidateException(f"该工具提供者名字{req.name}已存在")

        headers = [h.model_dump() for h in req.headers]
        provider = ApiToolProvider(
            account_id=account.id,
            name=req.name,
            icon=req.icon,
            description=openapi_schema.description,
            openapi_schema=req.openapi_schema,
            headers=headers,
        )
        db.add(provider)
        await db.flush()

        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                db.add(
                    ApiTool(
                        account_id=account.id,
                        provider_id=provider.id,
                        name=method_item.get("operationId"),
                        description=method_item.get("description"),
                        url=f"{openapi_schema.server}{path}",
                        method=method,
                        parameters=method_item.get("parameters", []),
                    )
                )
        await db.commit()

    @staticmethod
    async def update_api_tool_provider(
        provider_id: UUID,
        req: UpdateApiToolProviderReq,
        account: Account,
        db: AsyncSession,
    ) -> None:
        """根据传递的 provider_id + req 更新对应的 API 工具提供者信息"""
        provider = await ApiToolService._get_provider_owned(provider_id, account, db)
        openapi_schema = ApiToolService.parse_openapi_schema(req.openapi_schema)

        # 同名检测（排除自身）
        result = await db.execute(
            select(ApiToolProvider).where(
                ApiToolProvider.account_id == account.id,
                ApiToolProvider.name == req.name,
                ApiToolProvider.id != provider.id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ValidateException(f"该工具提供者名字{req.name}已存在")

        # 删除旧工具
        await db.execute(
            delete(ApiTool).where(
                ApiTool.provider_id == provider.id,
                ApiTool.account_id == account.id,
            )
        )

        # 更新提供者
        headers = [h.model_dump() for h in req.headers]
        provider.name = req.name
        provider.icon = req.icon
        provider.headers = headers
        provider.description = openapi_schema.description
        provider.openapi_schema = req.openapi_schema

        # 新增工具
        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                db.add(
                    ApiTool(
                        account_id=account.id,
                        provider_id=provider.id,
                        name=method_item.get("operationId"),
                        description=method_item.get("description"),
                        url=f"{openapi_schema.server}{path}",
                        method=method,
                        parameters=method_item.get("parameters", []),
                    )
                )
        await db.commit()

    @staticmethod
    async def get_api_tool_providers_with_page(
        req: GetApiToolProvidersWithPageReq, account: Account, db: AsyncSession
    ) -> PageData[GetApiToolProvidersWithPageResp]:
        """获取自定义 API 工具服务提供者分页列表数据"""
        filters = [ApiToolProvider.account_id == account.id]
        if req.search_word:
            filters.append(ApiToolProvider.name.ilike(f"%{req.search_word}%"))

        count_result = await db.execute(
            select(func.count()).select_from(ApiToolProvider).where(*filters)
        )
        total_record = count_result.scalar() or 0

        result = await db.execute(
            select(ApiToolProvider)
            .where(*filters)
            .order_by(desc(ApiToolProvider.created_at))
            .offset((req.current_page - 1) * req.page_size)
            .limit(req.page_size)
        )
        providers = result.scalars().all()

        items: list[GetApiToolProvidersWithPageResp] = []
        for provider in providers:
            tools = await ApiToolService._list_tools(provider.id, db)
            items.append(GetApiToolProvidersWithPageResp.from_model(provider, tools))

        return page_data(
            items,
            current_page=req.current_page,
            page_size=req.page_size,
            total_record=total_record,
        )

    @staticmethod
    async def get_api_tool(
        provider_id: UUID, tool_name: str, account: Account, db: AsyncSession
    ) -> GetApiToolResp:
        """根据传递的 provider_id + tool_name 获取对应工具的参数详情信息"""
        result = await db.execute(
            select(ApiTool).where(
                ApiTool.provider_id == provider_id,
                ApiTool.name == tool_name,
            )
        )
        api_tool = result.scalar_one_or_none()
        if api_tool is None or api_tool.account_id != account.id:
            raise NotFoundException("该工具不存在")

        # 手动加载 provider
        prov_result = await db.execute(
            select(ApiToolProvider).where(ApiToolProvider.id == provider_id)
        )
        api_tool.provider = prov_result.scalar_one()  # type: ignore[attr-defined]
        return GetApiToolResp.from_model(api_tool)

    @staticmethod
    async def get_api_tool_provider(
        provider_id: UUID, account: Account, db: AsyncSession
    ) -> GetApiToolProviderResp:
        """根据传递的 provider_id 获取 API 工具提供者信息"""
        provider = await ApiToolService._get_provider_owned(provider_id, account, db)
        return GetApiToolProviderResp.from_model(provider)

    @staticmethod
    async def delete_api_tool_provider(
        provider_id: UUID, account: Account, db: AsyncSession
    ) -> None:
        """根据传递的 provider_id 删除对应的工具提供商 + 工具的所有信息"""
        provider = await ApiToolService._get_provider_owned(provider_id, account, db)
        await db.execute(
            delete(ApiTool).where(
                ApiTool.provider_id == provider_id,
                ApiTool.account_id == account.id,
            )
        )
        await db.delete(provider)
        await db.commit()
