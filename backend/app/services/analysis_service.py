#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""应用统计分析服务（async，迁移自 imooc analysis_service.py）。

指标从 Postgres Message 表按最近 7 天 / 再往前 7 天计算环比，趋势按天聚合。
结果按自然日缓存到 Redis（1 天）。ClickHouse/Langfuse 后续可接观测，本接口不依赖。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.app import App
from app.models.conversation import Message
from app.services.app_service import AppService

logger = logging.getLogger(__name__)

_OVERVIEW_FIELDS = (
    "total_messages",
    "active_accounts",
    "avg_of_conversation_messages",
    "token_output_rate",
    "cost_consumption",
)


class AnalysisService:
    """统计分析服务"""

    @staticmethod
    def _cache_key(app_id: UUID, today: datetime) -> str:
        return f"analysis:{today.strftime('%Y_%m_%d')}:{app_id}"

    @staticmethod
    async def get_app_analysis(
        app_id: UUID,
        account: Account,
        db: AsyncSession,
        redis,
    ) -> dict[str, Any]:
        """根据传递的应用id+账号获取指定应用的分析信息"""
        app = await AppService.get_app(app_id, account, db)

        today = datetime.now()
        today_midnight = datetime.combine(today, datetime.min.time())
        seven_days_ago = today_midnight - timedelta(days=7)
        fourteen_days_ago = today_midnight - timedelta(days=14)
        cache_key = AnalysisService._cache_key(app.id, today)

        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            logger.exception("读取应用分析缓存失败, app_id=%s", app.id)

        seven_days_messages = await AnalysisService.get_messages_by_time_range(
            app, seven_days_ago, today_midnight, db
        )
        fourteen_days_messages = await AnalysisService.get_messages_by_time_range(
            app, fourteen_days_ago, seven_days_ago, db
        )

        seven_overview = AnalysisService.calculate_overview_indicators_by_messages(
            seven_days_messages
        )
        fourteen_overview = AnalysisService.calculate_overview_indicators_by_messages(
            fourteen_days_messages
        )
        pop = AnalysisService.calculate_pop_by_overview_indicators(
            seven_overview, fourteen_overview
        )
        trend = AnalysisService.calculate_trend_by_messages(
            today_midnight, 7, seven_days_messages
        )

        app_analysis = {
            **trend,
            **{
                field: {
                    "data": seven_overview.get(field),
                    "pop": pop.get(field),
                }
                for field in _OVERVIEW_FIELDS
            },
        }

        try:
            await redis.set(cache_key, json.dumps(app_analysis), ex=24 * 60 * 60)
        except Exception:
            logger.exception("写入应用分析缓存失败, app_id=%s", app.id)

        return app_analysis

    @staticmethod
    async def get_messages_by_time_range(
        app: App,
        start_at: datetime,
        end_at: datetime,
        db: AsyncSession,
    ) -> list[Message]:
        """根据传递的时间段获取指定应用的消息会话数据"""
        result = await db.execute(
            select(Message).where(
                Message.app_id == app.id,
                Message.created_at >= start_at,
                Message.created_at < end_at,
                Message.answer != "",
            )
        )
        return list(result.scalars().all())

    @classmethod
    def calculate_overview_indicators_by_messages(
        cls, messages: list[Any]
    ) -> dict[str, Any]:
        """根据消息列表计算概览指标"""
        total_messages = len(messages)
        active_accounts = len({message.created_by for message in messages})

        avg_of_conversation_messages = 0.0
        conversation_count = len({message.conversation_id for message in messages})
        if conversation_count != 0:
            avg_of_conversation_messages = total_messages / conversation_count

        token_output_rate = 0.0
        latency_sum = sum(float(message.latency or 0) for message in messages)
        if latency_sum != 0:
            token_output_rate = (
                sum(int(message.total_token_count or 0) for message in messages)
                / latency_sum
            )

        cost_consumption = sum(float(message.total_price or 0) for message in messages)

        return {
            "total_messages": total_messages,
            "active_accounts": active_accounts,
            "avg_of_conversation_messages": float(avg_of_conversation_messages),
            "token_output_rate": float(token_output_rate),
            "cost_consumption": float(cost_consumption),
        }

    @classmethod
    def calculate_pop_by_overview_indicators(
        cls, current_data: dict[str, Any], previous_data: dict[str, Any]
    ) -> dict[str, Any]:
        """根据当前数据+相邻时期数据计算环比增长"""
        pop: dict[str, Any] = {}
        for field in _OVERVIEW_FIELDS:
            current_value = current_data.get(field) or 0
            previous_value = previous_data.get(field) or 0
            if previous_value != 0:
                pop[field] = float((current_value - previous_value) / previous_value)
            else:
                pop[field] = 0
        return pop

    @classmethod
    def calculate_trend_by_messages(
        cls, end_at: datetime, days_ago: int, messages: list[Any]
    ) -> dict[str, Any]:
        """根据结束时间、回退天数、消息列表计算趋势数据"""
        end_at = datetime.combine(end_at, datetime.min.time())

        total_messages_trend: dict[str, list] = {"x_axis": [], "y_axis": []}
        active_accounts_trend: dict[str, list] = {"x_axis": [], "y_axis": []}
        avg_of_conversation_messages_trend: dict[str, list] = {"x_axis": [], "y_axis": []}
        cost_consumption_trend: dict[str, list] = {"x_axis": [], "y_axis": []}

        for day in range(days_ago):
            trend_start_at = end_at - timedelta(days_ago - day)
            trend_end_at = end_at - timedelta(days_ago - day - 1)
            day_messages = [
                message for message in messages
                if trend_start_at <= message.created_at < trend_end_at
            ]

            total_messages_trend_y_axis = len(day_messages)
            total_messages_trend["x_axis"].append(int(trend_start_at.timestamp()))
            total_messages_trend["y_axis"].append(total_messages_trend_y_axis)

            active_accounts_trend["x_axis"].append(int(trend_start_at.timestamp()))
            active_accounts_trend["y_axis"].append(
                len({message.created_by for message in day_messages})
            )

            avg_y = 0.0
            conversation_count = len({message.conversation_id for message in day_messages})
            if conversation_count != 0:
                avg_y = total_messages_trend_y_axis / conversation_count
            avg_of_conversation_messages_trend["x_axis"].append(int(trend_start_at.timestamp()))
            avg_of_conversation_messages_trend["y_axis"].append(float(avg_y))

            cost_y = sum(float(message.total_price or 0) for message in day_messages)
            cost_consumption_trend["x_axis"].append(int(trend_start_at.timestamp()))
            cost_consumption_trend["y_axis"].append(float(cost_y))

        return {
            "total_messages_trend": total_messages_trend,
            "active_accounts_trend": active_accounts_trend,
            "avg_of_conversation_messages_trend": avg_of_conversation_messages_trend,
            "cost_consumption_trend": cost_consumption_trend,
        }
