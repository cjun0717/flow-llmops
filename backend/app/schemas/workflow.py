#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流相关 Pydantic schema（迁移自 imooc workflow_schema.py）。"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.workflow.entities.workflow_entity import WORKFLOW_CONFIG_NAME_PATTERN
from app.entities.workflow_entity import WorkflowStatus
from app.lib.helper import datetime_to_timestamp
from app.models.workflow import Workflow


class CreateWorkflowReq(BaseModel):
    """创建工作流基础请求"""
    name: str = Field(..., max_length=50, description="工作流名称")
    tool_call_name: str = Field(..., max_length=50, description="英文名称")
    icon: str = Field(..., description="工作流图标URL")
    description: str = Field(..., max_length=1024, description="工作流描述")

    @field_validator("tool_call_name")
    @classmethod
    def validate_tool_call_name(cls, value: str) -> str:
        import re
        if not re.match(WORKFLOW_CONFIG_NAME_PATTERN, value):
            raise ValueError("英文名称仅支持字母、数字和下划线，且以字母/下划线为开头")
        return value


class UpdateWorkflowReq(BaseModel):
    """更新工作流基础请求"""
    name: str = Field(..., max_length=50, description="工作流名称")
    tool_call_name: str = Field(..., max_length=50, description="英文名称")
    icon: str = Field(..., description="工作流图标URL")
    description: str = Field(..., max_length=1024, description="工作流描述")

    @field_validator("tool_call_name")
    @classmethod
    def validate_tool_call_name(cls, value: str) -> str:
        import re
        if not re.match(WORKFLOW_CONFIG_NAME_PATTERN, value):
            raise ValueError("英文名称仅支持字母、数字和下划线，且以字母/下划线为开头")
        return value


class GetWorkflowsWithPageReq(BaseModel):
    """获取工作流分页列表数据请求结构"""
    current_page: int = Field(default=1, ge=1, le=9999, description="当前页数")
    page_size: int = Field(default=20, ge=1, le=50, description="每页条数")
    status: str = Field(default="", description="工作流状态")
    search_word: str = Field(default="", description="搜索词")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value and value not in WorkflowStatus.__members__.values():
            raise ValueError("工作流状态格式错误")
        return value


class GetWorkflowResp(BaseModel):
    """获取工作流详情响应结构"""
    id: UUID = Field(default=UUID(int=0))
    name: str = ""
    tool_call_name: str = ""
    icon: str = ""
    description: str = ""
    status: str = ""
    is_debug_passed: bool = False
    node_count: int = 0
    published_at: int = 0
    updated_at: int = 0
    created_at: int = 0

    @classmethod
    def from_model(cls, data: Workflow) -> "GetWorkflowResp":
        return cls(
            id=data.id,
            name=data.name,
            tool_call_name=data.tool_call_name,
            icon=data.icon,
            description=data.description,
            status=data.status,
            is_debug_passed=data.is_debug_passed,
            node_count=len(data.draft_graph.get("nodes", [])),
            published_at=datetime_to_timestamp(data.published_at),
            updated_at=datetime_to_timestamp(data.updated_at),
            created_at=datetime_to_timestamp(data.created_at),
        )


class GetWorkflowsWithPageResp(BaseModel):
    """获取工作流分页列表数据响应结构"""
    id: UUID = Field(default=UUID(int=0))
    name: str = ""
    tool_call_name: str = ""
    icon: str = ""
    description: str = ""
    status: str = ""
    is_debug_passed: bool = False
    node_count: int = 0
    published_at: int = 0
    updated_at: int = 0
    created_at: int = 0

    @classmethod
    def from_model(cls, data: Workflow) -> "GetWorkflowsWithPageResp":
        return cls(
            id=data.id,
            name=data.name,
            tool_call_name=data.tool_call_name,
            icon=data.icon,
            description=data.description,
            status=data.status,
            is_debug_passed=data.is_debug_passed,
            node_count=len(data.graph.get("nodes", [])),
            published_at=datetime_to_timestamp(data.published_at),
            updated_at=datetime_to_timestamp(data.updated_at),
            created_at=datetime_to_timestamp(data.created_at),
        )


class CreateWorkflowData(BaseModel):
    """创建工作流返回数据"""
    id: UUID
