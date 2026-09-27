#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置工具服务（迁移自 imooc builtin_tool_service.py）。"""
from __future__ import annotations

import mimetypes
import os.path
from typing import Any

from pydantic import BaseModel

from app.core.tools.builtin_tools.categories import BuiltinCategoryManager
from app.core.tools.builtin_tools.providers import BuiltinProviderManager
from app.exceptions import NotFoundException


class BuiltinToolService:
    """内置工具服务"""

    def __init__(
        self,
        builtin_provider_manager: BuiltinProviderManager,
        builtin_category_manager: BuiltinCategoryManager,
    ) -> None:
        self.builtin_provider_manager = builtin_provider_manager
        self.builtin_category_manager = builtin_category_manager

    def get_builtin_tools(self) -> list[dict]:
        """获取 LLMOps 项目中的所有内置提供商 + 工具对应的信息"""
        providers = self.builtin_provider_manager.get_providers()

        builtin_tools: list[dict] = []
        for provider in providers:
            provider_entity = provider.provider_entity
            builtin_tool: dict = {
                **provider_entity.model_dump(exclude=["icon"]),
                "tools": [],
            }

            for tool_entity in provider.get_tool_entities():
                tool = provider.get_tool(tool_entity.name)
                tool_dict = {
                    **tool_entity.model_dump(),
                    "inputs": self.get_tool_inputs(tool),
                }
                builtin_tool["tools"].append(tool_dict)

            builtin_tools.append(builtin_tool)

        return builtin_tools

    def get_provider_tool(self, provider_name: str, tool_name: str) -> dict:
        """根据传递的提供者名字 + 工具名字获取指定工具信息"""
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if provider is None:
            raise NotFoundException(f"该提供商{provider_name}不存在")

        tool_entity = provider.get_tool_entity(tool_name)
        if tool_entity is None:
            raise NotFoundException(f"该工具{tool_name}不存在")

        provider_entity = provider.provider_entity
        tool = provider.get_tool(tool_name)

        builtin_tool = {
            "provider": {**provider_entity.model_dump(exclude=["icon", "created_at"])},
            **tool_entity.model_dump(),
            "created_at": provider_entity.created_at,
            "inputs": self.get_tool_inputs(tool),
        }
        return builtin_tool

    def get_provider_icon(self, provider_name: str) -> tuple[bytes, str]:
        """根据传递的提供者名字获取 icon 流信息"""
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if not provider:
            raise NotFoundException(f"该工具提供者{provider_name}不存在")

        # 计算 provider 所在目录
        current_path = os.path.abspath(__file__)
        services_path = os.path.dirname(current_path)
        app_path = os.path.dirname(services_path)
        provider_path = os.path.join(
            app_path, "core", "tools", "builtin_tools", "providers", provider_name
        )

        icon_path = os.path.join(provider_path, "_asset", provider.provider_entity.icon)
        if not os.path.exists(icon_path):
            raise NotFoundException("该工具提供者_asset下未提供图标")

        mimetype, _ = mimetypes.guess_type(icon_path)
        mimetype = mimetype or "application/octet-stream"

        with open(icon_path, "rb") as f:
            byte_data = f.read()
            return byte_data, mimetype

    def get_categories(self) -> list[dict[str, Any]]:
        """获取所有的内置分类信息"""
        category_map = self.builtin_category_manager.get_category_map()
        return [
            {
                "name": category["entity"].name,
                "category": category["entity"].category,
                "icon": category["icon"],
            }
            for category in category_map.values()
        ]

    @classmethod
    def get_tool_inputs(cls, tool: Any) -> list[dict]:
        """根据传入的工具获取 inputs 信息"""
        inputs: list[dict] = []
        args_schema = getattr(tool, "args_schema", None)
        if isinstance(args_schema, type) and issubclass(args_schema, BaseModel):
            for field_name, model_field in args_schema.model_fields.items():
                annotation = model_field.annotation
                type_name = getattr(annotation, "__name__", str(annotation))
                inputs.append(
                    {
                        "name": field_name,
                        "description": model_field.description or "",
                        "required": model_field.is_required(),
                        "type": type_name,
                    }
                )
        return inputs
