from typing import int
from pydantic import BaseModel, Field
import uuid
from .response import ResponseBase

class AccountInfo(BaseModel):
    """账号信息模型"""
    id: uuid.UUID = Field(default=None, description="账号ID")
    name: str = Field(default="", description="账号昵称")
    email: str = Field(default="", description="邮箱/用户名")
    avatar: str = Field(default="", description="头像URL")
    last_login_at: int = Field(default=None, description="最后登录时间")
    last_login_ip: str = Field(default="", description="最后登录IP")
    created_at: int = Field(default=None, description="创建时间")

AccountInfoResponse = ResponseBase[AccountInfo]
