#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import PrimaryKeyConstraint, Index, Uuid
from .base_model import BaseModel

class EndUser(BaseModel):
    """终端用户表模型"""
    __tablename__ = "end_user"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_end_user_id"),
        Index("end_user_tenant_id_idx", "tenant_id"),
        Index("end_user_app_id_idx", "app_id"),
        {'comment': '终端用户表'}
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="归属的账号/空间id"
    )
    app_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        comment="归属应用的id，终端用户只能在应用下使用"
    )
