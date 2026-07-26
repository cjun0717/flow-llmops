#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""JWT 编解码工具。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt

from app.config import settings
from app.exceptions import UnauthorizedError

ALGORITHM = settings.ALGORITHM
ISS = "llmops"


def create_access_token(
    subject: str | UUID,
    *,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """生成 access_token，payload 含 sub / exp / iss（对齐 imooc）。"""
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iss": ISS,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def parse_access_token(token: str) -> dict[str, Any]:
    """解析并校验 access_token，失败抛 UnauthorizedError。"""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            issuer=ISS,
        )
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedError("授权认证凭证已过期请重新登陆") from e
    except jwt.InvalidTokenError as e:
        raise UnauthorizedError("解析token出错，请重新登陆") from e
