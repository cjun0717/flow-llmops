#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用统计分析路由（迁移自 imooc analysis_handler.py）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep, RedisDep
from app.schemas.analysis import AppAnalysisData
from app.schemas.response import ApiResponse, ok
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["应用统计"])


@router.get("/{app_id}", response_model=ApiResponse[AppAnalysisData])
async def get_app_analysis(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    redis: RedisDep,
) -> ApiResponse[AppAnalysisData]:
    """根据传递的应用id获取应用的统计信息"""
    data = await AnalysisService.get_app_analysis(app_id, account, db, redis)
    return ok(data)
