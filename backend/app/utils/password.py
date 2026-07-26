#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""密码哈希工具（对齐 imooc pbkdf2 规则，兼容旧库）。"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from typing import Any

# 至少包含一个字母、一个数字，长度 8-16
password_pattern = r"^(?=.*[a-zA-Z])(?=.*\d).{8,16}$"


def validate_password(password: str, pattern: str = password_pattern) -> None:
    """校验密码规则，不符合则抛 ValueError。"""
    if re.match(pattern, password) is None:
        raise ValueError("密码规则校验失败，至少包含一个字母，一个数字，并且长度为8-16位")


def hash_password(password: str, salt: Any) -> bytes:
    """password + salt → pbkdf2 哈希（hex bytes）。"""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 10000)
    return binascii.hexlify(dk)


def compare_password(
    password: str,
    password_hashed_base64: Any,
    salt_base64: Any,
) -> bool:
    """比对明文密码与库中 base64 存储的哈希/盐。"""
    return hash_password(password, base64.b64decode(salt_base64)) == base64.b64decode(
        password_hashed_base64
    )
