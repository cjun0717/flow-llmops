import logging

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from .database import AsyncSessionLocal, async_engine, Base

logger = logging.getLogger(__name__)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话依赖
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
        finally:
            await session.close()

async def init_create_table() -> None:
    """
    应用启动时初始化数据库连接

    :return:
    """
    logger.info('🔎 初始化数据库连接...')
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info('✅️ 数据库连接成功')


async def close_async_engine() -> None:
    """
    应用关闭时释放数据库连接池

    :return:
    """
    await async_engine.dispose()