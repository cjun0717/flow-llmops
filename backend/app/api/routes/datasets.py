#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库路由（CRUD + queries + hit 召回测试）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep, RetrievalServiceDep
from app.schemas.dataset import (
    CreateDatasetReq,
    DatasetDetailData,
    DatasetListItemData,
    DatasetQueryData,
    GetDatasetsWithPageReq,
    HitReq,
    HitRespItem,
    UpdateDatasetReq,
)
from app.schemas.response import ApiResponse, PageData, ok
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["知识库"])


@router.get("", response_model=ApiResponse[PageData[DatasetListItemData]])
async def get_datasets_with_page(
    account: CurrentAccount,
    db: AsyncSessionDep,
    search_word: str = Query("", description="搜索词"),
    current_page: int = Query(1, ge=1, le=9999, description="当前页数"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数"),
) -> ApiResponse[PageData[DatasetListItemData]]:
    """获取知识库分页列表"""
    req = GetDatasetsWithPageReq(
        search_word=search_word,
        current_page=current_page,
        page_size=page_size,
    )
    data = await DatasetService.get_datasets_with_page(req, account, db)
    return ok(data)


@router.post("", response_model=ApiResponse[dict])
async def create_dataset(
    body: CreateDatasetReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """创建知识库"""
    await DatasetService.create_dataset(body, account, db)
    return ok({}, message="创建知识库成功")


@router.get("/{dataset_id}", response_model=ApiResponse[DatasetDetailData])
async def get_dataset(
    dataset_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[DatasetDetailData]:
    """获取知识库详情"""
    data = await DatasetService.get_dataset_detail(dataset_id, account, db)
    return ok(data)


@router.post("/{dataset_id}", response_model=ApiResponse[dict])
async def update_dataset(
    dataset_id: UUID,
    body: UpdateDatasetReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """更新知识库"""
    await DatasetService.update_dataset(dataset_id, body, account, db)
    return ok({}, message="修改知识库成功")


@router.post("/{dataset_id}/delete", response_model=ApiResponse[dict])
async def delete_dataset(
    dataset_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """删除知识库"""
    await DatasetService.delete_dataset(dataset_id, account, db)
    return ok({}, message="删除知识库成功")


@router.get("/{dataset_id}/queries", response_model=ApiResponse[list[DatasetQueryData]])
async def get_dataset_queries(
    dataset_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[list[DatasetQueryData]]:
    """获取知识库最近查询记录"""
    data = await DatasetService.get_dataset_queries(dataset_id, account, db)
    return ok(data)


@router.post("/{dataset_id}/hit", response_model=ApiResponse[list[HitRespItem]])
async def hit(
    dataset_id: UUID,
    body: HitReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    retrieval_svc: RetrievalServiceDep,
) -> ApiResponse[list[HitRespItem]]:
    """知识库召回测试"""
    data = await DatasetService.hit(dataset_id, body, account, db, retrieval_svc)
    return ok(data)
