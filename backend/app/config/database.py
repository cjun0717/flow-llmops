from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncAttrs,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
from .config import settings

def create_async_db_engine() -> AsyncEngine:
    """
    创建异步 SQLAlchemy Engine

    :param echo: 可选，是否输出 SQLAlchemy SQL 日志
    :return: 异步 SQLAlchemy Engine
    """
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_size=settings.DB_POOL_SIZE,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_timeout=settings.DB_POOL_TIMEOUT,
    )
def create_async_session_local(engine: AsyncEngine) -> async_sessionmaker:
    """
    创建异步 Session 工厂

    :param engine: 异步 SQLAlchemy Engine
    :return: 异步 Session 工厂
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async_engine = create_async_db_engine()
AsyncSessionLocal = create_async_session_local(async_engine)

# 声明基类
class Base(AsyncAttrs, MappedAsDataclass, DeclarativeBase):
    """subclasses will be converted to dataclasses"""


