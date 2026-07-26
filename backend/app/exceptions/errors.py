#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""业务异常定义（对齐 imooc HttpCode）。"""
from __future__ import annotations

from typing import Any

from app.schemas.response import HttpCode


class AppException(Exception):
    """应用业务异常基类"""

    code: HttpCode = HttpCode.FAIL
    message: str = "服务器异常"
    data: Any = None

    def __init__(self, message: str | None = None, data: Any = None) -> None:
        self.message = message if message is not None else self.message
        self.data = data
        super().__init__(self.message)


class FailError(AppException):
    """通用失败"""

    code = HttpCode.FAIL
    message = "操作失败"


class NotFoundError(AppException):
    """资源不存在"""

    code = HttpCode.NOT_FOUND
    message = "资源不存在"


class UnauthorizedError(AppException):
    """未授权"""

    code = HttpCode.UNAUTHORIZED
    message = "未授权"


class ForbiddenError(AppException):
    """无权限"""

    code = HttpCode.FORBIDDEN
    message = "无权限"


class ValidateError(AppException):
    """数据验证失败"""

    code = HttpCode.VALIDATE_ERROR
    message = "数据验证失败"
