#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全局异常处理器：统一输出 ApiResponse 信封。"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.errors import AppException
from app.schemas.response import ApiResponse, HttpCode

logger = logging.getLogger(__name__)

# 业务异常与 HTTPException 先返回 HTTP 200，靠 body.code 区分（兼容现有 frontend）
_BUSINESS_HTTP_STATUS = 200

_HTTP_STATUS_TO_CODE: dict[int, HttpCode] = {
    400: HttpCode.FAIL,
    401: HttpCode.UNAUTHORIZED,
    403: HttpCode.FORBIDDEN,
    404: HttpCode.NOT_FOUND,
    422: HttpCode.VALIDATE_ERROR,
}


def _api_json(
    *,
    code: HttpCode,
    message: str = "",
    data: Any = None,
    status_code: int = _BUSINESS_HTTP_STATUS,
) -> JSONResponse:
    body = ApiResponse(code=code, message=message, data=data)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """业务异常 → ApiResponse"""
    logger.warning(
        "Business exception %s %s: [%s] %s",
        request.method,
        request.url.path,
        exc.code.value,
        exc.message,
    )
    return _api_json(code=exc.code, message=exc.message, data=exc.data)


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """请求参数校验失败 → validate_error"""
    logger.warning(
        "Validation error %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return _api_json(
        code=HttpCode.VALIDATE_ERROR,
        message="请求参数校验失败",
        data=exc.errors(),
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Starlette/FastAPI HTTPException → 映射业务 code"""
    code = _HTTP_STATUS_TO_CODE.get(exc.status_code, HttpCode.FAIL)
    detail = exc.detail
    if isinstance(detail, str):
        message = detail
        data = None
    else:
        message = "请求失败"
        data = detail

    logger.warning(
        "HTTPException %s %s: status=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return _api_json(code=code, message=message, data=data)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常：记完整堆栈，对外隐藏细节"""
    logger.exception(
        "Unhandled exception %s %s",
        request.method,
        request.url.path,
    )
    return _api_json(code=HttpCode.FAIL, message="服务器内部错误，请稍后重试")


def register_exception_handlers(app: FastAPI) -> None:
    """在 create_app 中调用，注册全局异常处理"""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
