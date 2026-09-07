from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.main import api_router
from app.config import settings
from app.db import close_async_engine, init_create_table
from app.deps import close_redis
from app.exceptions import register_exception_handlers
from app.logging_config import setup_logging
from app.middlewares import register_middlewares

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    :param app: FastAPI对象
    :return: None
    """
    try:
        await init_create_table()
    except Exception:
        raise

    yield

    try:
        await close_redis()
    except Exception:
        logger.exception("关闭 Redis 失败")

    try:
        await close_async_engine()
    except Exception:
        logger.exception("关闭数据库引擎失败")


def create_app() -> FastAPI:
    """
    创建FastAPI应用

    :return: FastAPI对象
    """
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=f"{settings.APP_NAME}接口文档",
        root_path=settings.API_V1_STR,
        lifespan=lifespan,
    )

    # 注册异常处理器
    register_exception_handlers(app)
    # 注册中间件
    register_middlewares(app)
    # 注册API路由
    app.include_router(api_router)

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="app.main:create_app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=settings.APP_RELOAD,
        workers=settings.APP_WORKERS,
        factory=True,
    )
