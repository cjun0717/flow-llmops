#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置工具提供商工厂（读取 providers.yaml，构建 Provider 映射）。"""
from __future__ import annotations

import os.path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.core.tools.builtin_tools.entities import Provider, ProviderEntity


class BuiltinProviderManager(BaseModel):
    """内置工具提供商工厂（单例）"""

    provider_map: dict[str, Provider] = Field(default_factory=dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._get_provider_tool_map()

    def get_provider(self, provider_name: str) -> Provider | None:
        """根据名字获取服务提供商"""
        return self.provider_map.get(provider_name)

    def get_providers(self) -> list[Provider]:
        """获取所有服务提供商列表"""
        return list(self.provider_map.values())

    def get_provider_entities(self) -> list[ProviderEntity]:
        """获取所有服务提供商实体列表"""
        return [provider.provider_entity for provider in self.provider_map.values()]

    def get_tool(self, provider_name: str, tool_name: str) -> Any:
        """根据提供商名+工具名获取工具"""
        provider = self.get_provider(provider_name)
        if provider is None:
            return None
        return provider.get_tool(tool_name)

    def _get_provider_tool_map(self) -> None:
        """初始化时读取 providers.yaml 并构建 provider_map"""
        if self.provider_map:
            return

        current_path = os.path.abspath(__file__)
        providers_path = os.path.dirname(current_path)
        providers_yaml_path = os.path.join(providers_path, "providers.yaml")

        with open(providers_yaml_path, encoding="utf-8") as f:
            providers_yaml_data = yaml.safe_load(f)

        for idx, provider_data in enumerate(providers_yaml_data):
            provider_entity = ProviderEntity(**provider_data)
            self.provider_map[provider_entity.name] = Provider(
                name=provider_entity.name,
                position=idx + 1,
                provider_entity=provider_entity,
            )
