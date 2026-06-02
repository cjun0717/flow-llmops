from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from config.get_db import close_async_engine, init_create_table
from fastapi.middleware.cors import CORSMiddleware
from api.main import api_router
from config import settings
# 生命周期事件
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    :param app: FastAPI对象
    :return: None
    """
    # 应用启动时：初始化数据库表（创建所有模型对应的表）
    try:
        await init_create_table()
    except Exception as e:
        raise  # 初始化失败直接终止应用启动，避免服务启动后无表可用
    
    yield
    # 应用关闭时：清理数据库引擎资源（关键！释放连接池）
    try:
        await close_async_engine()
    except Exception as e:
        print(f"❌ 关闭数据库引擎失败：{e}")


def create_app() -> FastAPI:
    """
    创建FastAPI应用

    :return: FastAPI对象
    """
    # 初始化FastAPI对象
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        description=f'{settings.APP_NAME}接口文档',
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 自定义API文档路由，修复无法直接通过后端地址访问文档的问题
    #APIDocsUtil.custom_api_docs_router(app)

    # 挂载子应用
    #handle_sub_applications(app)
    # 加载中间件处理方法
    #handle_middleware(app)
    # 加载全局异常处理方法
    #handle_exception(app)
    # 自动注册路由
    #auto_register_routers(app)
    app.include_router(api_router,prefix=settings.API_V1_STR)

    return app

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        app='main:create_app',
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        root_path=settings.APP_ROOT_PATH,
        reload=settings.APP_RELOAD,
        workers=settings.APP_WORKERS,
        factory=True,
    )