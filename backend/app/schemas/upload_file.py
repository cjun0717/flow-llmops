#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""上传文件相关 Schema。"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.upload_file import UploadFile


def _datetime_to_timestamp(dt: datetime | None) -> int:
    if dt is None:
        return 0
    return int(dt.timestamp())


class UploadFileData(BaseModel):
    """上传文件响应 data"""

    id: UUID
    account_id: UUID
    name: str
    key: str
    size: int
    extension: str
    mime_type: str
    created_at: int

    @classmethod
    def from_model(cls, f: UploadFile) -> "UploadFileData":
        return cls(
            id=f.id,
            account_id=f.account_id,
            name=f.name,
            key=f.key,
            size=f.size,
            extension=f.extension,
            mime_type=f.mime_type,
            created_at=_datetime_to_timestamp(f.created_at),
        )


class UploadImageData(BaseModel):
    """上传图片响应 data"""

    image_url: str
