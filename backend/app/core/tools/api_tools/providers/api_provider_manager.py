#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""API 工具提供者管理器：根据配置生成自定义 LangChain 工具。"""
from __future__ import annotations

from typing import Callable, Optional, Type

import requests
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from app.core.tools.api_tools.entities import ParameterIn, ParameterTypeMap, ToolEntity


class ApiProviderManager(BaseModel):
    """API 工具提供者管理器，根据传递的工具配置信息生成自定义 LangChain 工具"""

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def _create_tool_func_from_tool_entity(cls, tool_entity: ToolEntity) -> Callable:
        """根据传递的信息创建发起 API 请求的函数"""

        def tool_func(**kwargs) -> str:
            parameters = {
                ParameterIn.PATH: {},
                ParameterIn.HEADER: {},
                ParameterIn.QUERY: {},
                ParameterIn.COOKIE: {},
                ParameterIn.REQUEST_BODY: {},
            }

            parameter_map = {
                parameter.get("name"): parameter for parameter in tool_entity.parameters
            }
            header_map = {header.get("key"): header.get("value") for header in tool_entity.headers}

            for key, value in kwargs.items():
                parameter = parameter_map.get(key)
                if parameter is None:
                    continue
                parameters[parameter.get("in", ParameterIn.QUERY)][key] = value

            return requests.request(
                method=tool_entity.method,
                url=tool_entity.url.format(**parameters[ParameterIn.PATH]),
                params=parameters[ParameterIn.QUERY],
                json=parameters[ParameterIn.REQUEST_BODY],
                headers={**header_map, **parameters[ParameterIn.HEADER]},
                cookies=parameters[ParameterIn.COOKIE],
            ).text

        return tool_func

    @classmethod
    def _create_model_from_parameters(cls, parameters: list[dict]) -> Type[BaseModel]:
        """根据传递的 parameters 参数创建 BaseModel 子类"""
        fields = {}
        for parameter in parameters:
            field_name = parameter.get("name")
            field_type = ParameterTypeMap.get(parameter.get("type"), str)
            field_required = parameter.get("required", True)
            field_description = parameter.get("description", "")
            field_default = ... if field_required else None

            fields[field_name] = (
                field_type if field_required else Optional[field_type],
                Field(default=field_default, description=field_description),
            )

        return create_model("DynamicModel", **fields)

    def get_tool(self, tool_entity: ToolEntity) -> BaseTool:
        """根据传递的配置获取自定义 API 工具"""
        return StructuredTool.from_function(
            func=self._create_tool_func_from_tool_entity(tool_entity),
            name=f"{tool_entity.id}_{tool_entity.name}",
            description=tool_entity.description,
            args_schema=self._create_model_from_parameters(tool_entity.parameters),
        )
