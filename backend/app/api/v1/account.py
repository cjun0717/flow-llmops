

from fastapi import APIRouter
from services import AccountService
from schemas import AccountInfoResponse, ResponseBase
from schemas import response_resp
from api.deps import CurrentUser
from api.deps import SessionDB
router = APIRouter(prefix="/account", tags=["账号管理模块"])

@router.get(
    "",
    summary="获取当前登录账号信息",
    response_model=AccountInfoResponse
)
async def get_account_info(current_user: CurrentUser):
    """获取当前登录账号信息"""
    result = AccountService.get_account_info(current_user)
    return response_resp(data=result)

@router.post(
    "/password",
    summary="修改当前登录账号密码",
    response_model=ResponseBase
)
async def update_password(
    db: SessionDB,
    current_user: CurrentUser,
    data: dict
):
    """修改当前登录账号密码"""
    password = data.get("password")
    await AccountService.update_password(db,password,current_user)
    return response_resp(message="修改当前登录账号密码成功")


@router.post(
    "/name",
    summary="修改当前登录账号名称",
    response_model=ResponseBase
)
async def update_name(
    db: SessionDB,
    current_user: CurrentUser,
    data: dict
):
    """修改当前登录账号名称"""
    name = data.get("name")
    await AccountService.update_name(db,name,current_user)
    return response_resp(message="修改账号名称成功")

@router.post(
    "/avatar",
    summary="修改当前登录账号头像",
    response_model=ResponseBase
)
async def update_avatar(
    db: SessionDB,
    current_user: CurrentUser,
    data: dict
):
    """修改当前登录账号头像"""
    avatar = data.get("avatar")
    await AccountService.update_avatar(db, avatar, current_user)
    return response_resp(message="修改账号头像成功")


