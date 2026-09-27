#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""会话管理路由（CRUD）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep
from app.schemas.conversation import (
    GetConversationMessagesWithPageReq,
    MessageItem,
    UpdateConversationIsPinnedReq,
    UpdateConversationNameReq,
)
from app.schemas.response import ApiResponse, PageData, ok
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["会话管理"])


@router.get("/{conversation_id}/messages", response_model=ApiResponse[PageData[MessageItem]])
async def get_conversation_messages_with_page(
    conversation_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
    created_at: int = Query(0, ge=0, description="created_at游标，0代表不限制"),
) -> ApiResponse[PageData[MessageItem]]:
    """根据传递的会话id获取该会话的消息列表分页数据"""
    req = GetConversationMessagesWithPageReq(
        current_page=current_page, page_size=page_size, created_at=created_at
    )
    data = await ConversationService.get_conversation_messages_with_page(
        conversation_id, req, account, db
    )
    return ok(data)


@router.post("/{conversation_id}/delete", response_model=ApiResponse[dict])
async def delete_conversation(
    conversation_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """根据传递的会话id删除指定的会话"""
    await ConversationService.delete_conversation(conversation_id, account, db)
    return ok({}, message="删除会话成功")


@router.post(
    "/{conversation_id}/messages/{message_id}/delete",
    response_model=ApiResponse[dict],
)
async def delete_message(
    conversation_id: UUID,
    message_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """根据传递的会话id+消息id删除指定的消息"""
    await ConversationService.delete_message(conversation_id, message_id, account, db)
    return ok({}, message="删除会话消息成功")


@router.get("/{conversation_id}/name", response_model=ApiResponse[dict])
async def get_conversation_name(
    conversation_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """根据传递的会话id获取指定会话的名字"""
    conversation = await ConversationService.get_conversation(conversation_id, account, db)
    return ok({"name": conversation.name})


@router.post("/{conversation_id}/name", response_model=ApiResponse[dict])
async def update_conversation_name(
    conversation_id: UUID,
    body: UpdateConversationNameReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """根据传递的会话id+name更新会话名字"""
    await ConversationService.update_conversation(
        conversation_id, account, db, name=body.name
    )
    return ok({}, message="修改会话名称成功")


@router.post("/{conversation_id}/is-pinned", response_model=ApiResponse[dict])
async def update_conversation_is_pinned(
    conversation_id: UUID,
    body: UpdateConversationIsPinnedReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """根据传递的会话id+is_pinned更新会话的置顶状态"""
    await ConversationService.update_conversation(
        conversation_id, account, db, is_pinned=body.is_pinned
    )
    return ok({}, message="修改会话置顶状态成功")
