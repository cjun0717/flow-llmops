#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, text, Uuid

from app.database import Base

class BaseModel(Base):
    """
    公共基础模型：ID由业务生成，包含通用的创建/更新时间
    """
    __abstract__ = True  # 抽象类，不生成实际表

    # 1. 主键ID（由业务代码生成，删除数据库自动生成逻辑）
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,  # 通用 UUID 类型，自动适配不同数据库
        primary_key=True,
        nullable=False,
        comment="配置id"
    )

    # 2. 创建时间（仅创建时赋值，无onupdate）
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        comment="创建时间"
    )

    # 3. 更新时间（创建时赋值，更新时自动刷新）
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=text("CURRENT_TIMESTAMP(0)"),  # 数据库自动刷新更新时间
        comment="更新时间"
    )
