#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用统计分析 Schema（对齐前端 models/analysis.ts）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class IndicatorItem(BaseModel):
    """概览指标：当前值 + 环比"""
    data: float = 0
    pop: float = 0


class TrendItem(BaseModel):
    """近 7 天趋势：x 为日期时间戳，y 为对应数值"""
    x_axis: list[int] = Field(default_factory=list)
    y_axis: list[float] = Field(default_factory=list)


class AppAnalysisData(BaseModel):
    """获取应用统计分析响应数据"""
    total_messages: IndicatorItem = Field(default_factory=IndicatorItem)
    active_accounts: IndicatorItem = Field(default_factory=IndicatorItem)
    avg_of_conversation_messages: IndicatorItem = Field(default_factory=IndicatorItem)
    token_output_rate: IndicatorItem = Field(default_factory=IndicatorItem)
    cost_consumption: IndicatorItem = Field(default_factory=IndicatorItem)
    total_messages_trend: TrendItem = Field(default_factory=TrendItem)
    active_accounts_trend: TrendItem = Field(default_factory=TrendItem)
    avg_of_conversation_messages_trend: TrendItem = Field(default_factory=TrendItem)
    cost_consumption_trend: TrendItem = Field(default_factory=TrendItem)
