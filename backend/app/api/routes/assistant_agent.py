#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""辅助智能体路由（迁移自 imooc assistant_agent_handler.py）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAccount
from app.deps import (
    AsyncSessionDep,
    AssistantKnowledgeServiceDep,
    LanguageModelServiceDep,
    SyncRedisDep,
)
from app.schemas.assistant_agent import (
    AssistantAgentChatReq,
    GetAssistantAgentMessagesWithPageReq,
)
from app.schemas.conversation import MessageItem
from app.schemas.response import ApiResponse, PageData, ok
from app.services.assistant_agent_service import AssistantAgentService

router = APIRouter(prefix="/assistant-agent", tags=["辅助Agent"])


@router.post("/chat")
async def assistant_agent_chat(
    body: AssistantAgentChatReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    language_model_service: LanguageModelServiceDep,
    knowledge_service: AssistantKnowledgeServiceDep,
    sync_redis: SyncRedisDep,
) -> StreamingResponse:
    """与辅助智能体进行对话聊天（SSE 流式）"""
    generator = AssistantAgentService.chat(
        body, account, db, language_model_service, knowledge_service, sync_redis
    )
    return StreamingResponse(
        generator,
        status_code=200,
        media_type="text/event-stream",
    )


@router.post("/chat/{task_id}/stop", response_model=ApiResponse[dict])
async def stop_assistant_agent_chat(
    task_id: UUID,
    account: CurrentAccount,
    sync_redis: SyncRedisDep,
) -> ApiResponse[dict]:
    """停止与辅助智能体的对话聊天"""
    AssistantAgentService.stop_chat(task_id, account, sync_redis)
    return ok({}, message="停止辅助Agent会话成功")


@router.get("/messages", response_model=ApiResponse[PageData[MessageItem]])
async def get_assistant_agent_messages_with_page(
    account: CurrentAccount,
    db: AsyncSessionDep,
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
    created_at: int = Query(0, ge=0, description="created_at游标，0代表不限制"),
) -> ApiResponse[PageData[MessageItem]]:
    """获取与辅助智能体的消息分页列表"""
    req = GetAssistantAgentMessagesWithPageReq(
        current_page=current_page, page_size=page_size, created_at=created_at
    )
    data = await AssistantAgentService.get_conversation_messages_with_page(
        req, account, db
    )
    return ok(data)


@router.post("/delete-conversation", response_model=ApiResponse[dict])
async def delete_assistant_agent_conversation(
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """清空/删除与辅助智能体的聊天会话记录"""
    await AssistantAgentService.delete_conversation(account, db)
    return ok({}, message="清空辅助Agent会话成功")
