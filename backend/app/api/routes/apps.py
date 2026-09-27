#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用管理路由（CRUD）。"""
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAccount
from app.deps import (
    AppConfigServiceDep,
    AsyncSessionDep,
    LanguageModelServiceDep,
    RetrievalServiceDep,
    SyncRedisDep,
)
from app.schemas.app import (
    AppDetailData,
    AppListItemData,
    CreateAppReq,
    CreateAppData,
    FallbackHistoryToDraftReq,
    GetAppsWithPageReq,
    GetPublishHistoriesWithPageReq,
    PublishHistoryItem,
    PublishedConfigData,
    UpdateAppReq,
    UpdateDraftAppConfigReq,
)
from app.schemas.conversation import (
    DebugChatReq,
    GetDebugConversationMessagesWithPageReq,
    GetDebugConversationSummaryData,
    MessageItem,
    UpdateDebugConversationSummaryReq,
)
from app.schemas.response import ApiResponse, PageData, ok
from app.services.app_service import AppService

router = APIRouter(prefix="/apps", tags=["应用管理"])


@router.get("", response_model=ApiResponse[PageData[AppListItemData]])
async def get_apps_with_page(
    account: CurrentAccount,
    db: AsyncSessionDep,
    search_word: str = Query("", description="搜索词"),
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
) -> ApiResponse[PageData[AppListItemData]]:
    """获取当前登录账号的应用分页列表"""
    req = GetAppsWithPageReq(
        search_word=search_word,
        current_page=current_page,
        page_size=page_size,
    )
    data = await AppService.get_apps_with_page(req, account, db)
    return ok(data)


@router.post("", response_model=ApiResponse[CreateAppData])
async def create_app(
    body: CreateAppReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[CreateAppData]:
    """创建应用"""
    app = await AppService.create_app(body, account, db)
    return ok(CreateAppData(id=app.id))


@router.get("/{app_id}", response_model=ApiResponse[AppDetailData])
async def get_app(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[AppDetailData]:
    """获取应用详情"""
    data = await AppService.get_app_detail(app_id, account, db)
    return ok(data)


@router.post("/{app_id}", response_model=ApiResponse[dict])
async def update_app(
    app_id: UUID,
    body: UpdateAppReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """修改应用基础信息"""
    await AppService.update_app(app_id, body, account, db)
    return ok({}, message="修改Agent智能体应用成功")


@router.post("/{app_id}/delete", response_model=ApiResponse[dict])
async def delete_app(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """删除应用"""
    await AppService.delete_app(app_id, account, db)
    return ok({}, message="删除Agent智能体应用成功")


@router.post("/{app_id}/copy", response_model=ApiResponse[CreateAppData])
async def copy_app(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[CreateAppData]:
    """复制应用"""
    app = await AppService.copy_app(app_id, account, db)
    return ok(CreateAppData(id=app.id))


# ===== 阶段7：配置与发布 =====


@router.get("/{app_id}/draft-app-config", response_model=ApiResponse[dict])
async def get_draft_app_config(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
) -> ApiResponse[dict]:
    """获取应用草稿配置"""
    data = await AppService.get_draft_app_config(app_id, account, db, app_config_service)
    return ok(data)


@router.post("/{app_id}/draft-app-config", response_model=ApiResponse[dict])
async def update_draft_app_config(
    app_id: UUID,
    body: UpdateDraftAppConfigReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
) -> ApiResponse[dict]:
    """更新应用草稿配置"""
    # 仅传递非 None 字段
    draft = body.model_dump(by_alias=True, exclude_none=True)
    await AppService.update_draft_app_config(app_id, draft, account, db, app_config_service)
    return ok({}, message="更新应用草稿配置成功")


@router.post("/{app_id}/publish", response_model=ApiResponse[dict])
async def publish_app(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
) -> ApiResponse[dict]:
    """发布应用草稿配置为运行时配置"""
    await AppService.publish_draft_app_config(app_id, account, db, app_config_service)
    return ok({}, message="发布应用成功")


@router.post("/{app_id}/cancel-publish", response_model=ApiResponse[dict])
async def cancel_publish(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """取消发布应用"""
    await AppService.cancel_publish_app_config(app_id, account, db)
    return ok({}, message="取消发布应用成功")


@router.get("/{app_id}/publish-histories", response_model=ApiResponse[PageData[PublishHistoryItem]])
async def get_publish_histories_with_page(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
) -> ApiResponse[PageData[PublishHistoryItem]]:
    """获取应用发布历史配置分页列表"""
    req = GetPublishHistoriesWithPageReq(current_page=current_page, page_size=page_size)
    data = await AppService.get_publish_histories_with_page(app_id, req, account, db)
    return ok(data)


@router.post("/{app_id}/fallback-history", response_model=ApiResponse[dict])
async def fallback_history_to_draft(
    app_id: UUID,
    body: FallbackHistoryToDraftReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
) -> ApiResponse[dict]:
    """回退历史版本配置到草稿"""
    await AppService.fallback_history_to_draft(
        app_id, body.app_config_version_id, account, db, app_config_service
    )
    return ok({}, message="回退历史版本到草稿成功")


@router.get("/{app_id}/published-config", response_model=ApiResponse[PublishedConfigData])
async def get_published_config(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[PublishedConfigData]:
    """获取应用已发布配置"""
    data = await AppService.get_published_config(app_id, account, db)
    return ok(PublishedConfigData(web_app=data["web_app"]))


@router.post("/{app_id}/published-config/regenerate-web-app-token", response_model=ApiResponse[dict])
async def regenerate_web_app_token(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """重新生成 WebApp 凭证标识"""
    token = await AppService.regenerate_web_app_token(app_id, account, db)
    return ok({"token": token}, message="重新生成WebApp凭证标识成功")


# ===== 阶段8：调试会话与流式 =====


@router.get("/{app_id}/summary", response_model=ApiResponse[GetDebugConversationSummaryData])
async def get_debug_conversation_summary(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
) -> ApiResponse[GetDebugConversationSummaryData]:
    """根据传递的应用id获取调试会话长期记忆"""
    summary = await AppService.get_debug_conversation_summary(app_id, account, db, app_config_service)
    return ok(GetDebugConversationSummaryData(summary=summary))


@router.post("/{app_id}/summary", response_model=ApiResponse[dict])
async def update_debug_conversation_summary(
    app_id: UUID,
    body: UpdateDebugConversationSummaryReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
) -> ApiResponse[dict]:
    """根据传递的应用id+摘要信息更新调试会话长期记忆"""
    await AppService.update_debug_conversation_summary(
        app_id, body.summary, account, db, app_config_service
    )
    return ok({}, message="更新AI应用长期记忆成功")


@router.post("/{app_id}/conversations/delete-debug-conversation", response_model=ApiResponse[dict])
async def delete_debug_conversation(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """根据传递的应用id，清空该应用的调试会话记录"""
    await AppService.delete_debug_conversation(app_id, account, db)
    return ok({}, message="清空应用调试会话记录成功")


@router.post("/{app_id}/conversations")
async def debug_chat(
    app_id: UUID,
    body: DebugChatReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
    language_model_service: LanguageModelServiceDep,
    retrieval_service: RetrievalServiceDep,
    sync_redis: SyncRedisDep,
) -> StreamingResponse:
    """根据传递的应用id+query，发起调试对话（SSE 流式事件输出）"""
    generator = AppService.debug_chat(
        app_id, body, account, db, app_config_service,
        language_model_service, retrieval_service, sync_redis,
    )
    return StreamingResponse(
        generator,
        status_code=200,
        media_type="text/event-stream",
    )


@router.post("/{app_id}/conversations/tasks/{task_id}/stop", response_model=ApiResponse[dict])
async def stop_debug_chat(
    app_id: UUID,
    task_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    sync_redis: SyncRedisDep,
) -> ApiResponse[dict]:
    """根据传递的应用id+任务id停止某个应用的指定调试会话"""
    await AppService.stop_debug_chat(app_id, task_id, account, db, sync_redis)
    return ok({}, message="停止应用调试会话成功")


@router.get("/{app_id}/conversations/messages", response_model=ApiResponse[PageData[MessageItem]])
async def get_debug_conversation_messages_with_page(
    app_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    app_config_service: AppConfigServiceDep,
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
    created_at: int = Query(0, ge=0, description="created_at游标，0代表不限制"),
) -> ApiResponse[PageData[MessageItem]]:
    """根据传递的应用id，获取该应用的调试会话分页列表记录"""
    req = GetDebugConversationMessagesWithPageReq(
        current_page=current_page, page_size=page_size, created_at=created_at
    )
    data = await AppService.get_debug_conversation_messages_with_page(
        app_id, req, account, db, app_config_service
    )
    return ok(data)
