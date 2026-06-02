
from fastapi import APIRouter, UploadFile
from services import AccountService
from schemas import AccountInfoResponse, ResponseBase
from schemas import response_resp,UploadFileResp
from api.deps import SessionDB, CurrentUser, MinioClient
from services import UploadFileService
router = APIRouter(prefix="/upload-files", tags=["文件上传模块"])

@router.post(
    "/file",
    summary="上传文件",
    response_model=UploadFileResp
)
async def upload_file(
    file: UploadFile,
    current_user: CurrentUser,
    db: SessionDB,
    minio_client: MinioClient,
):
    """上传文件"""
    file_content = await file.read()
    file_size = len(file_content)
    file_origin_name = file.filename
    result = await UploadFileService.upload_file(
        file_content,
        file_size,
        file.content_type,
        file_origin_name,
        current_user,
        db,
        minio_client
    )
    return response_resp(result)



@router.post(
    "/image",
    summary="上传图片",
)
async def upload_file(
    file: UploadFile,
    current_user: CurrentUser,
    db: SessionDB,
    minio_client: MinioClient,
):
    """上传图片"""
    file_content = await file.read()
    file_size = len(file_content)
    file_origin_name = file.filename
    result = await UploadFileService.upload_file(
        file_content,
        file_size,
        file.content_type,
        file_origin_name,
        current_user,
        db,
        minio_client
    )

    # 生成图片URL
    image_url = await UploadFileService.get_file_url(result.key)

    return response_resp(data={"image_url": image_url})