#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""上传文件服务（MinIO 对象存储）。"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import uuid
from datetime import datetime

from fastapi import UploadFile
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import FailException
from app.models.account import Account
from app.models.upload_file import UploadFile

logger = logging.getLogger(__name__)

# 允许上传的文件扩展名（对齐 imooc upload_file_entity.py）
ALLOWED_IMAGE_EXTENSION = ["jpg", "jpeg", "png", "webp", "gif", "svg"]
ALLOWED_DOCUMENT_EXTENSION = [
    "txt", "markdown", "md", "pdf", "html", "htm",
    "xlsx", "xls", "doc", "docx", "csv",
]

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB

_PUBLIC_READ_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{settings.MINIO_BUCKET}/*"],
        }
    ],
}


class UploadFileService:
    """MinIO 文件上传"""

    @staticmethod
    def ensure_bucket(client: Minio) -> None:
        """桶不存在则创建，并开放匿名读（浏览器才能直接显示图标）。"""
        bucket = settings.MINIO_BUCKET
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        try:
            client.set_bucket_policy(bucket, json.dumps(_PUBLIC_READ_POLICY))
        except Exception:
            logger.warning("设置 MinIO 公开读策略失败，图标可能无法显示", exc_info=True)

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
        """浏览器可访问的文件 URL（走 FastAPI 反代，不直连 MinIO 私有桶）。"""
        prefix = settings.SERVICE_API_PREFIX.rstrip("/")
        return f"{prefix}/upload-files/preview/{key}"

    @staticmethod
    def to_browser_url(url: str) -> str:
        """把已入库的 MinIO 直链改写成后端预览地址。"""
        if not url:
            return url
        prefixes = [
            f"{settings.MINIO_BASE_URL.rstrip('/')}/{settings.MINIO_BUCKET}/",
            f"http://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}/",
        ]
        for prefix in prefixes:
            if url.startswith(prefix):
                return UploadFileService.get_file_url(url[len(prefix):])
        return url
