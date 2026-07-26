#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""请求日志中间件：记录 method/path/status/耗时。"""
from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """记录每个请求的 method/path/status/耗时。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            cost_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "%s %s failed after %.1fms",
                request.method,
                request.url.path,
                cost_ms,
            )
            raise

        cost_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            cost_ms,
        )
        return response
