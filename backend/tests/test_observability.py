#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Langfuse 回调与默认账号种子的轻量测试。"""
from __future__ import annotations

from unittest.mock import patch

from app.core.observability.langfuse import get_langfuse_handler, langfuse_callbacks


def test_langfuse_callbacks_disabled():
    get_langfuse_handler.cache_clear()
    with patch("app.core.observability.langfuse.settings") as mock_settings:
        mock_settings.LANGFUSE_ENABLED = False
        mock_settings.LANGFUSE_PUBLIC_KEY = "pk"
        mock_settings.LANGFUSE_SECRET_KEY = "sk"
        mock_settings.LANGFUSE_HOST = "http://localhost:3000"
        get_langfuse_handler.cache_clear()
        assert langfuse_callbacks() == []
    get_langfuse_handler.cache_clear()


def test_langfuse_callbacks_missing_keys():
    get_langfuse_handler.cache_clear()
    with patch("app.core.observability.langfuse.settings") as mock_settings:
        mock_settings.LANGFUSE_ENABLED = True
        mock_settings.LANGFUSE_PUBLIC_KEY = ""
        mock_settings.LANGFUSE_SECRET_KEY = ""
        mock_settings.LANGFUSE_HOST = "http://localhost:3000"
        get_langfuse_handler.cache_clear()
        assert langfuse_callbacks() == []
    get_langfuse_handler.cache_clear()
