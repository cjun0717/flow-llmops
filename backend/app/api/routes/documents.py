#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文档路由（CRUD，迁移自 imooc document_handler.py）。"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep, RedisDep
from app.schemas.document import (
    CreateDocumentsData,
    CreateDocumentsReq,
    DocumentDetailData,
    DocumentListItemData,
    GetDocumentsWithPageReq,
    UpdateDocumentEnabledReq,
    UpdateDocumentNameReq,
)
from app.schemas.response import ApiResponse, PageData, ok
from app.services.document_service import DocumentService

router = APIRouter(tags=["文档"])


@router.get(
    "/datasets/{dataset_id}/documents",
    response_model=ApiResponse[PageData[DocumentListItemData]],
)
async def get_documents_with_page(
    dataset_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
    search_word: str = Query("", description="搜索词"),
    current_page: int = Query(1, ge=1, le=9999),
    page_size: int = Query(20, ge=1, le=50),
) -> ApiResponse[PageData[DocumentListItemData]]:
    """获取文档分页列表"""
    req = GetDocumentsWithPageReq(
        search_word=search_word,
        current_page=current_page,
        page_size=page_size,
    )
    data = await DocumentService.get_documents_with_page(dataset_id, req, account, db)
    return ok(data)


@router.post(
    "/datasets/{dataset_id}/documents",
    response_model=ApiResponse[CreateDocumentsData],
)
async def create_documents(
    dataset_id: UUID,
    body: CreateDocumentsReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[CreateDocumentsData]:
    """创建文档列表（触发异步构建任务）"""
    documents, batch = await DocumentService.create_documents(dataset_id, body, account, db)
    return ok(CreateDocumentsData(
        documents=[
            {
                "id": str(d.id),
                "name": d.name,
                "status": d.status,
                "created_at": int(d.created_at.timestamp()) if d.created_at else 0,
            }
            for d in documents
        ],
        batch=batch,
    ))


@router.get(
    "/datasets/{dataset_id}/documents/{document_id}",
    response_model=ApiResponse[DocumentDetailData],
)
async def get_document(
    dataset_id: UUID,
    document_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[DocumentDetailData]:
    """获取文档详情"""
    data = await DocumentService.get_document_detail(dataset_id, document_id, account, db)
    return ok(data)


@router.post(
    "/datasets/{dataset_id}/documents/{document_id}/name",
    response_model=ApiResponse[dict],
)
async def update_document_name(
    dataset_id: UUID,
    document_id: UUID,
    body: UpdateDocumentNameReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """更新文档名称"""
    await DocumentService.update_document_name(dataset_id, document_id, body.name, account, db)
    return ok({}, message="修改文档名称成功")


@router.post(
    "/datasets/{dataset_id}/documents/{document_id}/enabled",
    response_model=ApiResponse[dict],
)
async def update_document_enabled(
    dataset_id: UUID,
    document_id: UUID,
    body: UpdateDocumentEnabledReq,
    account: CurrentAccount,
    db: AsyncSessionDep,
    redis: RedisDep,
) -> ApiResponse[dict]:
    """更新文档启用状态"""
    await DocumentService.update_document_enabled(
        dataset_id, document_id, body.enabled, account, db, redis
    )
    return ok({}, message="修改文档启用状态成功")


@router.post(
    "/datasets/{dataset_id}/documents/{document_id}/delete",
    response_model=ApiResponse[dict],
)
async def delete_document(
    dataset_id: UUID,
    document_id: UUID,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[dict]:
    """删除文档"""
    await DocumentService.delete_document(dataset_id, document_id, account, db)
    return ok({}, message="删除文档成功")


@router.get(
    "/datasets/{dataset_id}/documents/batch/{batch}",
    response_model=ApiResponse[list[dict]],
)
async def get_documents_status(
    dataset_id: UUID,
    batch: str,
    account: CurrentAccount,
    db: AsyncSessionDep,
) -> ApiResponse[list[dict]]:
    """获取批次文档处理状态"""
    data = await DocumentService.get_documents_status(dataset_id, batch, account, db)
    return ok(data)
