#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""统一 API 响应与分页模型（契约对齐 imooc-llmops / 现有 frontend）。"""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HttpCode(str, Enum):
    """业务状态码（字符串，与前端 / API 文档一致）"""

    SUCCESS = "success"
    FAIL = "fail"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    VALIDATE_ERROR = "validate_error"


class ApiResponse(BaseModel, Generic[T]):
    """统一响应信封：{code, data, message}"""

    code: HttpCode = HttpCode.SUCCESS
    message: str = ""
    data: T | None = None


class PaginatorInfo(BaseModel):
    """分页元信息"""

    current_page: int = 1
    page_size: int = 20
    total_page: int = 0
    total_record: int = 0


class PageData(BaseModel, Generic[T]):
    """分页 data 体：{list, paginator}"""

    list: List[T] = Field(default_factory=list)
    paginator: PaginatorInfo


class PageParams(BaseModel):
    """列表接口查询参数（可作为 Query 依赖）"""

    current_page: int = Field(default=1, ge=1, le=9999, description="当前页数")
    page_size: int = Field(default=20, ge=1, le=50, description="每页条数")


def build_paginator(
    *,
    current_page: int,
    page_size: int,
    total_record: int,
) -> PaginatorInfo:
    """根据总数计算分页元信息"""
    total_page = math.ceil(total_record / page_size) if page_size > 0 and total_record > 0 else 0
    return PaginatorInfo(
        current_page=current_page,
        page_size=page_size,
        total_page=total_page,
        total_record=total_record,
    )


def page_data(
    items: List[T],
    *,
    current_page: int,
    page_size: int,
    total_record: int,
) -> PageData[T]:
    """组装分页 data"""
    return PageData(
        list=items,
        paginator=build_paginator(
            current_page=current_page,
            page_size=page_size,
            total_record=total_record,
        ),
    )


def ok(data: Any = None, message: str = "") -> ApiResponse[Any]:
    """成功响应"""
    return ApiResponse(code=HttpCode.SUCCESS, message=message, data=data)


def fail(
    message: str = "",
    *,
    code: HttpCode = HttpCode.FAIL,
    data: Any = None,
) -> ApiResponse[Any]:
    """失败响应（业务层也可直接 raise，由异常处理器统一包装）"""
    return ApiResponse(code=code, message=message, data=data)
