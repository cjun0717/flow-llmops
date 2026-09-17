#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""上传文件服务（MinIO 对象存储）。"""
from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime

from fastapi import UploadFile
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import FailException
from app.models.account import Account
from app.models.upload_file import UploadFile

# 允许上传的文件扩展名（对齐 imooc upload_file_entity.py）
ALLOWED_IMAGE_EXTENSION = ["jpg", "jpeg", "png", "webp", "gif", "svg"]
ALLOWED_DOCUMENT_EXTENSION = [
    "txt", "markdown", "md", "pdf", "html", "htm",
    "xlsx", "xls", "doc", "docx", "csv",
]

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB


class UploadFileService:
    """MinIO 文件上传"""

    @staticmethod
    def ensure_bucket(client: Minio) -> None:
        """桶不存在则创建（首次上传时调用）"""
        bucket = settings.MINIO_BUCKET
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

    @staticmethod
    async def upload_file(
        *,
        file: UploadFile,
        only_image: bool,
        account: Account,
        db: AsyncSession,
        minio_client: Minio,
    ) -> UploadFile:
        """上传文件到 MinIO，并写 upload_file 记录"""
        # 1.提取文件扩展名并校验
        filename = file.filename or ""
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in (ALLOWED_IMAGE_EXTENSION + ALLOWED_DOCUMENT_EXTENSION):
            raise FailException(f"该.{extension}扩展的文件不允许上传")
        if only_image and extension not in ALLOWED_IMAGE_EXTENSION:
            raise FailException(f"该.{extension}扩展的文件不支持上传，请上传正确的图片")

        # 2.读取文件内容并校验大小
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise FailException("上传文件最大不能超过15MB")

        # 3.生成云端 key：{年}/{月:02d}/{日:02d}/{uuid}.{ext}
        now = datetime.now()
        random_filename = f"{uuid.uuid4()}.{extension}"
        object_key = f"{now.year}/{now.month:02d}/{now.day:02d}/{random_filename}"

        # 4.上传到 MinIO
        try:
            UploadFileService.ensure_bucket(minio_client)
            minio_client.put_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=object_key,
                data=io.BytesIO(content),
                length=len(content),
                content_type=file.content_type or "application/octet-stream",
            )
        except Exception:
            raise FailException("上传文件失败，请稍后重试")

        # 5.写 upload_file 记录
        upload_file = UploadFile(
            account_id=account.id,
            name=filename,
            key=object_key,
            size=len(content),
            extension=extension,
            mime_type=file.content_type or "",
            hash=hashlib.sha3_256(content).hexdigest(),
        )
        db.add(upload_file)
        await db.commit()
        await db.refresh(upload_file)
        return upload_file

    @staticmethod
    def get_file_url(key: str) -> str:
        """根据 key 拼接文件访问 URL"""
        return f"{settings.MINIO_BASE_URL}/{settings.MINIO_BUCKET}/{key}"
