from fastapi import APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from schemas import TokenResponse
from api.deps import SessionDB
from typing import Annotated
from fastapi import Depends
from services import AuthService
from fastapi import Request
from schemas.response import response_resp
from api.deps import CurrentUser
router = APIRouter(prefix="/auth", tags=["登录模块"])

@router.post(
    "/password-login",
    summary="用户登录",
    response_model=TokenResponse
)
async def password_login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: SessionDB,
    request: Request,
):  
    """用户登录"""
    
    result = await AuthService.password_login(
        db=db,
        username=form_data.username,
        password=form_data.password,
        request = request
    )

    return response_resp(
        data=result
    )

@router.post(
    "/logout",
    summary="退出登录",
)
async def logout(
    current_user: CurrentUser
):
    return response_resp(
        message="退出当前账号成功",
    )
