#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置工具服务提供商实体（映射 providers.yaml + positions.yaml + {tool}.yaml）。"""
from __future__ import annotations

import os.path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.lib.helper import dynamic_import
from app.core.tools.builtin_tools.entities.tool_entity import ToolEntity


class ProviderEntity(BaseModel):
    """服务提供商实体，映射 providers.yaml 中的每条记录"""

    name: str
    label: str
    description: str
    icon: str
    background: str
    category: str
    created_at: int = 0


class Provider(BaseModel):
    """服务提供商，可获取其下所有工具/描述/图标等"""

    name: str
    position: int
    provider_entity: ProviderEntity
    tool_entity_map: dict[str, ToolEntity] = Field(default_factory=dict)
    tool_func_map: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._provider_init()

    def get_tool(self, tool_name: str) -> Any:
        """根据工具名获取工具函数"""
        return self.tool_func_map.get(tool_name)

    def get_tool_entity(self, tool_name: str) -> ToolEntity | None:
        """根据工具名获取工具实体"""
        return self.tool_entity_map.get(tool_name)

    def get_tool_entities(self) -> list[ToolEntity]:
        """获取所有工具实体列表"""
        return list(self.tool_entity_map.values())

    def _provider_init(self) -> None:
        """服务提供商初始化：读取 positions.yaml + {tool}.yaml，动态导入工具函数"""
        # 1.计算 provider 所在目录
        current_path = os.path.abspath(__file__)
        entities_path = os.path.dirname(current_path)
        provider_path = os.path.join(os.path.dirname(entities_path), "providers", self.name)

        # 2.读取 positions.yaml
        positions_yaml_path = os.path.join(provider_path, "positions.yaml")
        with open(positions_yaml_path, encoding="utf-8") as f:
            positions_yaml_data = yaml.safe_load(f)

        # 3.循环读取工具
        for tool_name in positions_yaml_data:
            tool_yaml_path = os.path.join(provider_path, f"{tool_name}.yaml")
            with open(tool_yaml_path, encoding="utf-8") as f:
                tool_yaml_data = yaml.safe_load(f)

            self.tool_entity_map[tool_name] = ToolEntity(**tool_yaml_data)
            self.tool_func_map[tool_name] = dynamic_import(
                f"app.core.tools.builtin_tools.providers.{self.name}",
                tool_name,
            )
