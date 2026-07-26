#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""标准库 logging 配置（控制台 + 滚动文件）。"""
from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from app.config import settings

# backend/app/logging_config.py -> backend/logs
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_FILE = LOG_DIR / "app.log"


def setup_logging() -> None:
    """初始化全局日志，应在 create_app 最早调用。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_level = "DEBUG" if settings.DEBUG else "INFO"
    console_level = "DEBUG" if settings.DEBUG else "INFO"

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": console_level,
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "filename": str(LOG_FILE),
                    "maxBytes": 10 * 1024 * 1024,
                    "backupCount": 5,
                    "encoding": "utf-8",
                    "level": "DEBUG",
                },
            },
            "loggers": {
                # 降低第三方噪音
                "uvicorn.access": {"level": "INFO"},
                "sqlalchemy.engine": {"level": "WARNING"},
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
            },
            "root": {
                "handlers": ["console", "file"],
                "level": root_level,
            },
        }
    )

    logging.getLogger(__name__).info(
        "Logging initialized (level=%s, file=%s)",
        root_level,
        LOG_FILE,
    )
