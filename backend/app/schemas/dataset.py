from turtle import update
from pydantic import BaseModel, Field
from .response import ResponseBase
from .response import PageInfo
import uuid

class DatasetInfo(BaseModel):
    id: uuid.UUID = Field(description="知识库ID")
    name: str = Field(description="知识库名称")
    icon: str = Field(description="知识库图标")
    description: str = Field(description="知识库描述")
    document_count: int = Field(default=0, description="知识库文档数量")
    character_count: int = Field(default=0, description="知识库拥有的文档总字符数量")
    related_app_count: int = Field(default=0, description="关联的APP应用数量")
    updated_at: int = Field(default=0, description="更新时间,时间戳")
    created_at: int = Field(default=0, description="创建时间,时间戳")
    
DatasetInfoResponse = ResponseBase[PageInfo[DatasetInfo]]