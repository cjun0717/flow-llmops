from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from app.deps import AsyncSessionDep
from app.exceptions import FailException
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/password-login")
async def login(
    db: AsyncSessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    account = await AuthService.password_login(form_data.username, form_data.password, db)

    if not account:
        raise FailException("账号不存在或者密码错误，请核实后重试")
    
    
