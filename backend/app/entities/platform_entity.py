#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第三方平台枚举（对齐 imooc platform_entity.py）。"""
from __future__ import annotations

from enum import Enum


class WechatConfigStatus(str, Enum):
    """微信配置状态"""
    CONFIGURED = "configured"
    UNCONFIGURED = "unconfigured"
