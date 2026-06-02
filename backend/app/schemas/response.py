from email import message
from pydantic import BaseModel
from typing import Any, Optional
from pydantic import Field
from fastapi.responses import JSONResponse
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class HttpCode(int, Enum):
    SUCCESS = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    MOVED_PERM = 301
    SEE_OTHER = 303
    NOT_MODIFIED = 304
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    BAD_METHOD = 405
    CONFLICT = 409
    UNSUPPORTED_TYPE = 415
    ERROR = 500
    NOT_IMPLEMENTED = 501
    WARN = 601
class HttpCodeMsg(str, Enum):
    SUCCESS = "操作成功"
    CREATED = "对象创建成功"
    ACCEPTED = "请求已经被接受"
    NO_CONTENT = "操作已经执行成功，但是没有返回数据"
    MOVED_PERM = "资源已被移除"
    SEE_OTHER = "重定向"
    NOT_MODIFIED = "资源没有被修改"
    BAD_REQUEST = "参数列表错误（缺少，格式不匹配）"
    UNAUTHORIZED = "未授权"
    FORBIDDEN = "访问受限，授权过期"
    NOT_FOUND = "资源，服务未找到"
    BAD_METHOD = "不允许的http方法"
    CONFLICT = "资源冲突，或者资源被锁"
    UNSUPPORTED_TYPE = "不支持的数据，媒体类型"
    ERROR = "系统内部错误"
    NOT_IMPLEMENTED = "接口未实现"
    WARN = "系统警告消息"
    

class ResponseBase(BaseModel, Generic[T]):
    code: int = Field(default=HttpCode.SUCCESS, description="响应状态码")
    message: str = Field(default=HttpCodeMsg.SUCCESS.value, description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")

    @field_validator("message", mode="before")
    @classmethod
    def set_default_message(cls, v):
        """当message为None时，设置默认值"""
        return HttpCodeMsg.SUCCESS.value if v is None else v

class Page(BaseModel):
    total_page: int = Field(default=0, description="总页数")  # 总页数
    total_record: int = Field(default=0, description="总记录数")  # 总条数
    current_page: int = Field(default=1, description="当前页数")  # 当前页数
    page_size: int = Field(default=20, description="每页条数")  # 每页条数

class PageInfo(BaseModel, Generic[T]):
    """分页响应模型"""
    list: list[T] = Field(default=None, description="响应数据列表")
    paginator: Page = Field(default=None, description="分页信息")

def response_resp(
    *,
    code: HttpCode = HttpCode.SUCCESS,
    message: HttpCodeMsg = HttpCodeMsg.SUCCESS.value,
    data: dict = {},
    http_status: int = 200
) -> JSONResponse:
    """统一出口，可手动指定 HTTP 状态码"""
    return JSONResponse(
        status_code=http_status,
        content=ResponseBase(code=code, message=message, data=data)
    )
