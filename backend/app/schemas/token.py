from typing import int
from .response import ResponseBase
from pydantic import BaseModel
### 响应模型 ###
class Token(BaseModel):
    """Token响应模型"""
    access_token: str = Field(default="", description="访问令牌")
    expires_at: int = Field(default=None, description="令牌过期时间")

TokenResponse = ResponseBase[Token]