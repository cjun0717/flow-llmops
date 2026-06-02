from tkinter import NO
import uuid
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from models import UploadFile
from .response import ResponseBase

class UploadFileResp(BaseModel):
    """上传文件接口响应模型"""
    id: Optional[uuid.UUID] = None
    account_id: Optional[str] = None
    name: Optional[str] = None
    key: Optional[str] = None
    size: Optional[int] = None
    extension: Optional[str] = None
    mime_type: Optional[str] = None
    created_at: Optional[int] = None

UploadFileResp =ResponseBase[UploadFileResp]