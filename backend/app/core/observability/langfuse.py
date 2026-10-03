#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Langfuse 追踪：替代 imooc 的 LangSmith（LANGCHAIN_TRACING_V2）。

LangChain 通过 CallbackHandler 上报；密钥与 Host 走 settings / 环境变量。
Langfuse 未启用或初始化失败时返回空回调，不影响主流程。
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def _sync_langfuse_env() -> None:
    """把 settings 同步到环境变量，供 Langfuse SDK 读取。"""
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
    if settings.LANGFUSE_SECRET_KEY:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
    if settings.LANGFUSE_HOST:
        os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)
        os.environ.setdefault("LANGFUSE_BASE_URL", settings.LANGFUSE_HOST)


@lru_cache
def get_langfuse_handler() -> Any | None:
    """进程内单例 CallbackHandler；未配置或失败则返回 None。"""
    if not settings.LANGFUSE_ENABLED:
        return None
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.info("Langfuse 未配置 PUBLIC/SECRET KEY，跳过 LLM 追踪")
        return None

    _sync_langfuse_env()
    try:
        from langfuse.langchain import CallbackHandler
        return CallbackHandler()
    except Exception as error:
        logger.warning("Langfuse CallbackHandler 初始化失败，跳过追踪: %s", error)
        return None


def langfuse_callbacks() -> list:
    """给 ChatOpenAI / load_language_model 用的 callbacks 列表。"""
    handler = get_langfuse_handler()
    return [handler] if handler is not None else []
