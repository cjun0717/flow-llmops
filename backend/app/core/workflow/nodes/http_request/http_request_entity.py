#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HTTP请求节点数据。"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field, HttpUrl, field_validator

from app.core.workflow.entities.node_entity import BaseNodeData
from app.core.workflow.entities.variable_entity import VariableEntity, VariableType, VariableValueType
from app.exceptions import ValidateException


class HttpRequestMethod(str, Enum):
    """Http请求方法类型枚举"""
    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    HEAD = "head"
    OPTIONS = "options"


class HttpRequestInputType(str, Enum):
    """Http请求输入变量类型"""
    PARAMS = "params"  # query参数
    HEADERS = "headers"  # header请求头
    BODY = "body"  # body参数


class HttpRequestNodeData(BaseNodeData):
    """HTTP请求节点数据"""
    url: Optional[HttpUrl] = None  # 请求URL地址
    method: HttpRequestMethod = HttpRequestMethod.GET  # API请求方法
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(
                name="status_code",
                type=VariableType.INT,
                value={"type": VariableValueType.GENERATED, "content": 0},
            ),
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED}),
        ],
    )

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, url):
        return url if url != "" else None

    @field_validator("outputs", mode="before")
    @classmethod
    def validate_outputs(cls, outputs):
        return [
            VariableEntity(
                name="status_code",
                type=VariableType.INT,
                value={"type": VariableValueType.GENERATED, "content": 0},
            ),
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED}),
        ]

    @field_validator("inputs")
    @classmethod
    def validate_inputs(cls, inputs):
        """校验输入列表数据"""
        for input in inputs:
            if input.meta.get("type") not in HttpRequestInputType.__members__.values():
                raise ValidateException("Http请求参数结构出错")
        return inputs
