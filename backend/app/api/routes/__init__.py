#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .auth import router as auth_router
from .account import router as account_router
from .oauth import router as oauth_router

__all__ = [
    "auth_router",
    "account_router",
    "oauth_router",
]
