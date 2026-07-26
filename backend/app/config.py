from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    RedisDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> repo root -> docker/.env
_ENV_FILE = Path(__file__).resolve().parents[2] / "docker" / ".env.development"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        cache_strings=True,
        extra="ignore",
    )
    APP_PORT: int = 8001
    APP_RELOAD: bool = True
    APP_WORKERS: int = 1
    APP_VERSION: str = "1.0"
    APP_NAME: str = "大模型应用开发平台"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    ###### 认证配置  ######
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SECRET_KEY: str = 'b01c66dc2c58dc6a0aabfe2144256be36226de378bf87f72c0c795dda67f4d55'
    ALGORITHM: str = "HS256"


    DB_TYPE: str = "postgresql"  # "mysql"
    DB_ECHO: bool = True
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_SIZE: int = 10
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_TIMEOUT: int = 300
    ###### postgresql数据库配置  ######
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_APP_DB: str

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return str(PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_APP_DB,
        ))
    ###### redis配置  ######
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_AUTH: str
    REDIS_DB: int = 0
    @computed_field
    @property
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_AUTH}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    ### minio配置###
    MINIO_HOST: str
    MINIO_CONSOLE_PORT: int
    MINIO_PORT: int
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str

    @computed_field
    @property
    def MINIO_ENDPOINT(self) -> str:
        return f"{self.MINIO_HOST}:{self.MINIO_PORT}"
    
    ### celery 配置###
    BROKER_DB: int = 1
    RESULT_DB: int = 2

    @computed_field
    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://:{self.REDIS_AUTH}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.BROKER_DB}"
    @computed_field
    @property
    def CELERY_RESULT_URL(self) -> str:
        return f"redis://:{self.REDIS_AUTH}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.RESULT_DB}"

settings = Settings()