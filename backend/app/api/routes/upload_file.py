#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文件上传路由。"""
from fastapi import APIRouter, UploadFile

from app.api.deps import CurrentAccount
from app.deps import AsyncSessionDep, MinioDep
from app.schemas.response import ApiResponse, ok
from app.schemas.upload_file import UploadFileData, UploadImageData
from app.services.upload_file_service import UploadFileService

router = APIRouter(prefix="/upload-files", tags=["文件上传"])


@router.post("/file", response_model=ApiResponse[UploadFileData])
async def upload_file(
    file: UploadFile,
    account: CurrentAccount,
    db: AsyncSessionDep,
    minio: MinioDep,
) -> ApiResponse[UploadFileData]:
    """上传文件/文档"""
    upload_file_record = await UploadFileService.upload_file(
        file=file,
        only_image=False,
        account=account,
        db=db,
        minio_client=minio,
    )
    return ok(UploadFileData.from_model(upload_file_record))


@router.post("/image", response_model=ApiResponse[UploadImageData])
async def upload_image(
    file: UploadFile,
    account: CurrentAccount,
    db: AsyncSessionDep,
    minio: MinioDep,
) -> ApiResponse[UploadImageData]:
    """上传图片"""
    upload_file_record = await UploadFileService.upload_file(
        file=file,
        only_image=True,
        account=account,
        db=db,
        minio_client=minio,
    )
    image_url = UploadFileService.get_file_url(upload_file_record.key)
    return ok(UploadImageData(image_url=image_url))
