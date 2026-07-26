#!/usr/bin/env python
# -*- coding: utf-8 -*-
import uuid
from datetime import datetime

from sqlalchemy import DateTime, text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BaseModel(Base):
    """公共基础模型：id / created_at / updated_at"""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("uuid_generate_v4()"),
        nullable=False,
        comment="主键id",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(0)"),
        onupdate=text("CURRENT_TIMESTAMP(0)"),
        comment="更新时间",
    )
