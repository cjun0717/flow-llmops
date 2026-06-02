
import uuid
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import hashlib
from datetime import datetime
from fastapi import HTTPException
from models import UploadFile, Account
from schemas import UploadFileResp
from config import settings
# 允许上传的文件类型
ALLOWED_IMAGE_EXTENSION = ["jpg", "jpeg", "png", "webp", "gif", "svg"]
ALLOWED_DOCUMENT_EXTENSION = ["txt", "markdown", "md", "pdf", "html", "htm", "xlsx", "xls", "doc", "docx", "csv"]

class UploadFileService:
    """上传文件服务"""

    @classmethod
    async def upload_file(
        cls,
        file_content: bytes,
        file_size: int,
        content_type: str,
        file_origin_name: str,
        account: Account,
        db: AsyncSession,
        minio_client: Minio
    ):
        """上传文件"""
        # 获取文件扩展名
        file_extension = file_origin_name.split(".")[-1]
        if file_extension.lower() not in ALLOWED_DOCUMENT_EXTENSION+ALLOWED_IMAGE_EXTENSION:
            raise HTTPException(status_code=400, detail="文件类型不支持")
        hash=hashlib.sha3_256(file_content).hexdigest() # 文件哈希值

        # 3.生成一个object_name
        random_filename = hash + "." + file_extension
        now = datetime.now()
        object_name = f"{now.year}/{now.month:02d}/{now.day:02d}/{random_filename}"
        
        if not cls._is_exists(account.id, object_name, minio_client):
            # 上传文件到MinIO
            minio_client.put_object(
                bucket_name=account.id,
                object_name=object_name,
                data=file_content,
                length=file_size,
                content_type=content_type,
            )
        # 插入数据库记录
        upload_file = UploadFile(
            id=uuid.uuid4(),
            account_id=account.id,
            name=file_origin_name,
            key=object_name,
            size=file_size,
            extension=file_extension,
            mime_type=content_type,
            hash=hash,
        )
        db.add(upload_file)
        await db.commit()
        await db.refresh(upload_file) 

        return UploadFileResp(
            id=upload_file.id,
            account_id=upload_file.account_id,
            name=upload_file.name,
            key=upload_file.key,
            size=upload_file.size,
            extension=upload_file.extension,
            mime_type=upload_file.mime_type,
            created_at=int(upload_file.created_at.timestamp()),
        )

            
    @classmethod
    def _is_exists(cls, bucket_name: str, object_name: str, minio_client: Minio):
        """
        判断bucker是否存在，不存在创建
        然后判断文件是否存在
        """
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
        try:
            minio_client.stat_object(bucket_name, object_name)
            return True
        except Exception as e:
            logging.warning(f"Fail to check, bucket_name={bucket_name}, object_name={object_name}, {str(e)}")
        return False

    @classmethod
    async def get_file_url(cls, key: str):
        """根据传递的key获取文件/图片的URL地址"""
        minio_base = f"http://{settings.MINIO_ENDPOINT}"
        
        return f"{minio_base}/{key}"
    



