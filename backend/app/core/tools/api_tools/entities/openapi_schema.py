#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenAPI 规范数据结构与校验。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.exceptions import ValidateException


class ParameterType(str, Enum):
    """参数支持的类型"""

    STR: str = "str"
    INT: str = "int"
    FLOAT: str = "float"
    BOOL: str = "bool"


ParameterTypeMap = {
    ParameterType.STR: str,
    ParameterType.INT: int,
    ParameterType.FLOAT: float,
    ParameterType.BOOL: bool,
}


class ParameterIn(str, Enum):
    """参数支持存放的位置"""

    PATH: str = "path"
    QUERY: str = "query"
    HEADER: str = "header"
    COOKIE: str = "cookie"
    REQUEST_BODY: str = "request_body"


class OpenAPISchema(BaseModel):
    """OpenAPI 规范的数据结构"""

    server: str = Field(default="", validate_default=True, description="工具提供者的服务基础地址")
    description: str = Field(default="", validate_default=True, description="工具提供者的描述信息")
    paths: dict[str, dict] = Field(
        default_factory=dict, validate_default=True, description="工具提供者的路径参数字典"
    )

    @field_validator("server", mode="before")
    def validate_server(cls, server: str) -> str:
        if server is None or server == "":
            raise ValidateException("server不能为空且为字符串")
        return server

    @field_validator("description", mode="before")
    def validate_description(cls, description: str) -> str:
        if description is None or description == "":
            raise ValidateException("description不能为空且为字符串")
        return description

    @field_validator("paths", mode="before")
    def validate_paths(cls, paths: dict[str, dict]) -> dict[str, dict]:
        if not paths or not isinstance(paths, dict):
            raise ValidateException("openapi_schema中的paths不能为空且必须为字典")

        methods = ["get", "post"]
        interfaces = []
        extra_paths = {}
        for path, path_item in paths.items():
            for method in methods:
                if method in path_item:
                    interfaces.append(
                        {
                            "path": path,
                            "method": method,
                            "operation": path_item[method],
                        }
                    )

        operation_ids = []
        for interface in interfaces:
            if not isinstance(interface["operation"].get("description"), str):
                raise ValidateException("description不能为空且为字符串")
            if not isinstance(interface["operation"].get("operationId"), str):
                raise ValidateException("operationId不能为空且为字符串")
            if not isinstance(interface["operation"].get("parameters", []), list):
                raise ValidateException("parameters必须是列表或者为空")

            if interface["operation"]["operationId"] in operation_ids:
                raise ValidateException(
                    f"operationId必须唯一，{interface['operation']['operationId']}出现重复"
                )
            operation_ids.append(interface["operation"]["operationId"])

            for parameter in interface["operation"].get("parameters", []):
                if not isinstance(parameter.get("name"), str):
                    raise ValidateException("parameter.name参数必须为字符串且不为空")
                if not isinstance(parameter.get("description"), str):
                    raise ValidateException("parameter.description参数必须为字符串且不为空")
                if not isinstance(parameter.get("required"), bool):
                    raise ValidateException("parameter.required参数必须为布尔值且不为空")
                if (
                    not isinstance(parameter.get("in"), str)
                    or parameter.get("in") not in ParameterIn.__members__.values()
                ):
                    raise ValidateException(
                        f"parameter.in参数必须为{'/'.join([item.value for item in ParameterIn])}"
                    )
                if (
                    not isinstance(parameter.get("type"), str)
                    or parameter.get("type") not in ParameterType.__members__.values()
                ):
                    raise ValidateException(
                        f"parameter.type参数必须为{'/'.join([item.value for item in ParameterType])}"
                    )

            extra_paths[interface["path"]] = {
                interface["method"]: {
                    "description": interface["operation"]["description"],
                    "operationId": interface["operation"]["operationId"],
                    "parameters": [
                        {
                            "name": parameter.get("name"),
                            "in": parameter.get("in"),
                            "description": parameter.get("description"),
                            "required": parameter.get("required"),
                            "type": parameter.get("type"),
                        }
                        for parameter in interface["operation"].get("parameters", [])
                    ],
                }
            }

        return extra_paths
