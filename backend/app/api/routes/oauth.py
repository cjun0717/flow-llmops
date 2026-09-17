#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第三方 OAuth（阶段 1 stub，后续再接真实提供商）。"""
from fastapi import APIRouter

from app.exceptions import FailException
from app.schemas.auth import OAuthAuthorizeReq, OAuthRedirectData, OAuthTokenData
from app.schemas.response import ApiResponse

router = APIRouter(prefix="/oauth", tags=["第三方授权"])


@router.get("/{provider_name}", response_model=ApiResponse[OAuthRedirectData])
async def get_oauth_redirect(provider_name: str) -> ApiResponse[OAuthRedirectData]:
    """获取第三方授权重定向地址（暂未实现）"""
    raise FailException(f"第三方登录暂未实现: {provider_name}")


@router.post("/authorize/{provider_name}", response_model=ApiResponse[OAuthTokenData])
async def oauth_authorize(
    provider_name: str,
    _body: OAuthAuthorizeReq,
) -> ApiResponse[OAuthTokenData]:
    """第三方授权回调（暂未实现）"""
    raise FailException(f"第三方登录暂未实现: {provider_name}")
