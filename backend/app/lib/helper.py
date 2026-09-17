#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通用辅助函数（迁移自 imooc internal/lib/helper.py）。"""
from __future__ import annotations

import importlib
import random
import string
from datetime import datetime
from enum import Enum
from hashlib import sha3_256
from typing import Any
from uuid import UUID

from pydantic import BaseModel


def dynamic_import(module_name: str, symbol_name: str) -> Any:
    """动态导入特定模块下的特定功能"""
    module = importlib.import_module(module_name)
    return getattr(module, symbol_name)


def generate_text_hash(text: str) -> str:
    """根据传递的文本计算对应的哈希值"""
    text = str(text) + "None"
    return sha3_256(text.encode()).hexdigest()


def datetime_to_timestamp(dt: datetime | None) -> int:
    """将传入的datetime时间转换成时间戳，如果数据不存在则返回0"""
    if dt is None:
        return 0
    return int(dt.timestamp())


def remove_fields(data_dict: dict, fields: list[str]) -> None:
    """根据传递的字段名移除字典中指定的字段"""
    for field in fields:
        data_dict.pop(field, None)


def convert_model_to_dict(obj: Any, *args, **kwargs) -> Any:
    """辅助函数，将Pydantic模型中的UUID/Enum等数据转换成可序列化存储的数据。"""
    if isinstance(obj, BaseModel):
        obj_dict = obj.model_dump(*args, **kwargs)
        for key, value in obj_dict.items():
            obj_dict[key] = convert_model_to_dict(value, *args, **kwargs)
        return obj_dict
    elif isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, list):
        return [convert_model_to_dict(item, *args, **kwargs) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_model_to_dict(value, *args, **kwargs) for key, value in obj.items()}
    return obj


def get_value_type(value: Any) -> Any:
    """根据传递的值获取变量的类型，并将str和bool转换成string和boolean"""
    value_type = type(value).__name__
    if value_type == "str":
        return "string"
    elif value_type == "bool":
        return "boolean"
    return value_type


def generate_random_string(length: int = 16) -> str:
    """根据传递的位数，生成随机字符串"""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))
