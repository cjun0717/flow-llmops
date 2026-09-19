from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncAttrs,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine
from pydantic import PostgresDsn
import logging

from .config import settings

logger = logging.getLogger(__name__)


def create_async_db_engine() -> AsyncEngine:
    """创建异步 SQLAlchemy Engine"""
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_size=settings.DB_POOL_SIZE,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_timeout=settings.DB_POOL_TIMEOUT,
    )


def create_async_session_local(engine: AsyncEngine) -> async_sessionmaker:
    """创建异步 Session 工厂"""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async_engine = create_async_db_engine()
AsyncSessionLocal = create_async_session_local(async_engine)


def _sync_database_url() -> str:
    """同步 DB URL（psycopg2）"""
    return str(PostgresDsn.build(
        scheme="postgresql+psycopg2",
        username=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        path=settings.POSTGRES_APP_DB,
    ))


sync_engine = create_engine(
    _sync_database_url(),
    echo=settings.DB_ECHO,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_size=settings.DB_POOL_SIZE,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, autoflush=False)


class Base(AsyncAttrs, DeclarativeBase):
    """SQLAlchemy 声明基类（异步）"""


async def init_create_table() -> None:
    """应用启动时创建所有模型对应的表"""
    import app.models  # noqa: F401

    logger.info("🔎 初始化数据库连接...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅️ 数据库连接成功")


async def close_async_engine() -> None:
    """应用关闭时释放数据库连接池"""
    await async_engine.dispose()


def close_sync_engine() -> None:
    """释放同步数据库连接池（Celery worker 退出时调用）"""
    sync_engine.dispose()
