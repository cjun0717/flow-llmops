#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Celery 应用（broker/result 用 Redis，与 imooc 一致）。"""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "flow-llmops",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_extended=True,
)

# 自动发现 tasks 模块
celery_app.autodiscover_tasks(["app.tasks"])
