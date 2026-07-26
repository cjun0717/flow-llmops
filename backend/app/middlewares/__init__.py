#!/usr/bin/env python
# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middlewares.request_log import RequestLogMiddleware


def register_middlewares(app: FastAPI) -> None:
    """
    统一注册中间件。

    注意 Starlette 后添加的中间件更靠外：
    请求顺序为 CORS → RequestLog → 路由。
    """
    # 先加内侧
    app.add_middleware(RequestLogMiddleware)
    # 再加外侧 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
