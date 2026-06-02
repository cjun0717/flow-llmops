from minio import Minio
from config import settings

_minio_client = None
async def get_minio_client():
    """获取Minio客户端"""
    if _minio_client is None:   
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=False,
        )
    return _minio_client
