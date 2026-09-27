#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI 辅助路由（迁移自 imooc ai_handler.py）。"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep
from app.schemas.ai import GenerateSuggestedQuestionsReq, OptimizePromptReq
from app.schemas.response import ApiResponse, ok
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI辅助"])


@router.post("/optimize-prompt")
async def optimize_prompt(
    body: OptimizePromptReq,
    account: CurrentAccount,
) -> StreamingResponse:
    """根据传递的预设 prompt 进行优化（SSE 流式输出）"""
    generator = AIService.optimize_prompt(body.prompt)
    return StreamingResponse(
        generator,
        status_code=200,
        media_type="text/event-stream",
    )


@router.post("/suggested-questions", response_model=ApiResponse[list[str]])
async def generate_suggested_questions(
    body: GenerateSuggestedQuestionsReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[list[str]]:
    """根据传递的消息 id 生成建议问题列表"""
    questions = await AIService.generate_suggested_questions_from_message_id(
        body.message_id, account, db
    )
    return ok(questions)
