#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文件上传路由。"""
from fastapi import APIRouter, Response, UploadFile
from minio.error import S3Error

from app.api.deps import CurrentAccount
from app.config import settings
from app.deps import AsyncSessionDep, MinioDep
from app.schemas.response import ApiResponse, ok
from app.schemas.upload_file import UploadFileData, UploadImageData
from app.services.upload_file_service import UploadFileService

router = APIRouter(prefix="/upload-files", tags=["文件上传"])


@router.get("/preview/{object_key:path}")
async def preview_file(
    object_key: str,
    minio: MinioDep,
) -> Response:
    """公开读取已上传文件，供 <img> 直接引用（无需 JWT）。"""
    try:
        obj = minio.get_object(settings.MINIO_BUCKET, object_key)
        try:
            data = obj.read()
            content_type = obj.headers.get("Content-Type") or "application/octet-stream"
        finally:
            obj.close()
            obj.release_conn()
    except S3Error:
        return Response(status_code=404)
    except Exception:
        return Response(status_code=404)
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


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
