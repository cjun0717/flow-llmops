#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Celery 任务：辅助 Agent 自动创建应用（迁移自 imooc task/app_task.py）。"""
from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.app_task.auto_create_app")
def auto_create_app(name: str, description: str, account_id: str) -> None:
    """根据传递的名称、描述、账号id创建一个 Agent"""
    from uuid import UUID

    from app.services.app_service import AppService

    AppService.auto_create_app(name, description, UUID(str(account_id)))
