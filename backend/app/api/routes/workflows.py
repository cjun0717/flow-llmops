#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流管理路由（9 端点，迁移自 imooc workflow_handler.py）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep
from app.schemas.response import ApiResponse, PageData, ok
from app.schemas.workflow import (
    CreateWorkflowData,
    CreateWorkflowReq,
    GetWorkflowResp,
    GetWorkflowsWithPageReq,
    GetWorkflowsWithPageResp,
    UpdateWorkflowReq,
)
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["工作流管理"])


@router.get("", response_model=ApiResponse[PageData[GetWorkflowsWithPageResp]])
async def get_workflows_with_page(
    account: CurrentAccount,
    db: AsyncSessionDep,
    search_word: str = Query("", description="搜索词"),
    status: str = Query("", description="工作流状态"),
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
) -> ApiResponse[PageData[GetWorkflowsWithPageResp]]:
    """获取当前登录账号的工作流分页列表"""
    req = GetWorkflowsWithPageReq(
        search_word=search_word,
        status=status,
        current_page=current_page,
        page_size=page_size,
    )
    data = await WorkflowService.get_workflows_with_page(req, account, db)
    return ok(data)


@router.post("", response_model=ApiResponse[CreateWorkflowData])
async def create_workflow(
    body: CreateWorkflowReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[CreateWorkflowData]:
    """新增工作流"""
    workflow = await WorkflowService.create_workflow(body, account, db)
    return ok(CreateWorkflowData(id=workflow.id))


@router.get("/{workflow_id}", response_model=ApiResponse[GetWorkflowResp])
async def get_workflow(
    workflow_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[GetWorkflowResp]:
    """获取工作流详情"""
    workflow = await WorkflowService.get_workflow(workflow_id, account, db)
    return ok(GetWorkflowResp.from_model(workflow))


@router.post("/{workflow_id}", response_model=ApiResponse[dict])
async def update_workflow(
    workflow_id: UUID,
    body: UpdateWorkflowReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """修改工作流基础信息"""
    await WorkflowService.update_workflow(workflow_id, account, body, db)
    return ok({}, message="修改工作流基础信息成功")


@router.post("/{workflow_id}/delete", response_model=ApiResponse[dict])
async def delete_workflow(
    workflow_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """删除工作流"""
    await WorkflowService.delete_workflow(workflow_id, account, db)
    return ok({}, message="删除工作流成功")


@router.post("/{workflow_id}/draft-graph", response_model=ApiResponse[dict])
async def update_draft_graph(
    workflow_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    body: dict,
) -> ApiResponse[dict]:
    """更新工作流草稿图配置"""
    await WorkflowService.update_draft_graph(workflow_id, body, account, db)
    return ok({}, message="更新工作流草稿配置成功")


@router.get("/{workflow_id}/draft-graph", response_model=ApiResponse[dict])
async def get_draft_graph(
    workflow_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    request: Request,
) -> ApiResponse[dict]:
    """获取工作流草稿配置信息"""
    base_url = str(request.base_url)
    draft_graph = await WorkflowService.get_draft_graph(workflow_id, account, db, base_url)
    return ok(draft_graph)


@router.post("/{workflow_id}/debug-workflow")
async def debug_workflow(
    workflow_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    body: dict,
) -> StreamingResponse:
    """根据传递的变量字典+工作流id调试指定的工作流（SSE 流式事件输出）"""
    generator = WorkflowService.debug_workflow(workflow_id, body, account, db)
    return StreamingResponse(
        generator,
        status_code=200,
        media_type="text/event-stream",
    )


@router.post("/{workflow_id}/publish", response_model=ApiResponse[dict])
async def publish_workflow(
    workflow_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """发布工作流"""
    await WorkflowService.publish_workflow(workflow_id, account, db)
    return ok({}, message="发布工作流成功")


@router.post("/{workflow_id}/cancel-publish", response_model=ApiResponse[dict])
async def cancel_publish_workflow(
    workflow_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """取消发布工作流"""
    await WorkflowService.cancel_publish_workflow(workflow_id, account, db)
    return ok({}, message="取消发布工作流成功")
