#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档片段路由（CRUD，同步写 Milvus）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep, RedisDep, SegmentServiceDep
from app.schemas.response import ApiResponse, PageData, ok
from app.schemas.segment import (
    CreateSegmentReq,
    GetSegmentsWithPageReq,
    SegmentDetailData,
    SegmentListItemData,
    UpdateSegmentEnabledReq,
    UpdateSegmentReq,
)

router = APIRouter(tags=["文档片段"])


@router.get(
    "/datasets/{dataset_id}/documents/{document_id}/segments",
    response_model=ApiResponse[PageData[SegmentListItemData]],
)
async def get_segments_with_page(
    dataset_id: UUID,
    document_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    svc: SegmentServiceDep,
    search_word: str = Query("", description="搜索词"),
    current_page: int = Query(1, ge=1, le=9999),
    page_size: int = Query(20, ge=1, le=50),
) -> ApiResponse[PageData[SegmentListItemData]]:
    """获取文档片段分页列表"""
    req = GetSegmentsWithPageReq(
        search_word=search_word,
        current_page=current_page,
        page_size=page_size,
    )
    data = await svc.get_segments_with_page(dataset_id, document_id, req, account, db)
    return ok(data)


@router.post(
    "/datasets/{dataset_id}/documents/{document_id}/segments",
    response_model=ApiResponse[dict],
)
async def create_segment(
    dataset_id: UUID,
    document_id: UUID,
    body: CreateSegmentReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    svc: SegmentServiceDep,
) -> ApiResponse[dict]:
    """新增文档片段（同步写 Milvus）"""
    await svc.create_segment(dataset_id, document_id, body, account, db)
    return ok({}, message="新增文档片段成功")


@router.get(
    "/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}",
    response_model=ApiResponse[SegmentDetailData],
)
async def get_segment(
    dataset_id: UUID,
    document_id: UUID,
    segment_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    svc: SegmentServiceDep,
) -> ApiResponse[SegmentDetailData]:
    """获取文档片段详情"""
    data = await svc.get_segment_detail(dataset_id, document_id, segment_id, account, db)
    return ok(data)


@router.post(
    "/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}",
    response_model=ApiResponse[dict],
)
async def update_segment(
    dataset_id: UUID,
    document_id: UUID,
    segment_id: UUID,
    body: UpdateSegmentReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    svc: SegmentServiceDep,
) -> ApiResponse[dict]:
    """更新文档片段"""
    await svc.update_segment(dataset_id, document_id, segment_id, body, account, db)
    return ok({}, message="修改文档片段成功")


@router.post(
    "/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}/enabled",
    response_model=ApiResponse[dict],
)
async def update_segment_enabled(
    dataset_id: UUID,
    document_id: UUID,
    segment_id: UUID,
    body: UpdateSegmentEnabledReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    redis: RedisDep,
    svc: SegmentServiceDep,
) -> ApiResponse[dict]:
    """更新文档片段启用状态"""
    await svc.update_segment_enabled(
        dataset_id, document_id, segment_id, body.enabled, account, db, redis
    )
    return ok({}, message="修改文档片段启用状态成功")


@router.post(
    "/datasets/{dataset_id}/documents/{document_id}/segments/{segment_id}/delete",
    response_model=ApiResponse[dict],
)
async def delete_segment(
    dataset_id: UUID,
    document_id: UUID,
    segment_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    svc: SegmentServiceDep,
) -> ApiResponse[dict]:
    """删除文档片段"""
    await svc.delete_segment(dataset_id, document_id, segment_id, account, db)
    return ok({}, message="删除文档片段成功")
