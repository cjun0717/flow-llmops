
from re import A
from fastapi import APIRouter, Query
from typing import Optional
from services import DatasetService
from schemas import ResponseBase, PageInfo
from schemas import response_resp
from api.deps import CurrentUser
from api.deps import SessionDB

router = APIRouter(prefix="/dataset", tags=["知识库模块"])


@router.get(
    "",
    response_model=ResponseBase,
    summary="4.1 获取知识库列表",
    description="用于获取当前登录账号的知识库列表信息，该接口支持搜索+分页，传递搜索词为空时代表不搜索。",
)
async def get_datasets_with_page(
    current_user: CurrentUser,
    db: SessionDB,
    search_word: Optional[str] = Query(None, description="搜索词"),
    current_page: int = Query(1, ge=1, description="当前页数"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
):
    """用于获取当前登录账号的知识库列表信息，该接口支持搜索+分页，传递搜索词为空时代表不搜索。"""
    result = await DatasetService.get_datasets_with_page(
        db,
        current_user,
        search_word,
        current_page,
        page_size,
    )
    return response_resp(data=result, message="获取知识库列表成功")


@router.post(
    "",
    response_model=ResponseBase,
    summary="4.2 创建知识库",
    description="根据传递的信息创建知识库，在同一个账号下，只能创建一个同名的知识库，避免在引用的时候发生误解",
)
async def create_dataset(
    current_user: CurrentUser,
    db: SessionDB,
    dataset: dict,
):
    """根据传递的信息创建知识库，在同一个账号下，只能创建一个同名的知识库，避免在引用的时候发生误解"""
    await DatasetService.create_dataset(
        db,
        current_user,
        dataset
    )
    return response_resp(message="创建知识库成功")


@router.delete(
    "/{dataset_id}",
    response_model=ResponseBase,
    summary="4.3 更新指定知识库信息",
    description="该接口主要用于更新指定的知识库信息，涵盖：知识库名称、图标、描述等信息。",
)
async def update_dataset(
    current_user: CurrentUser,
    db: SessionDB,
    dataset_id: str,
    dataset: dict,
):
    """该接口主要用于更新指定的知识库信息，涵盖：知识库名称、图标、描述等信息。"""
    await DatasetService.update_dataset(
        db,
        current_user,
        dataset_id,
        dataset
    )
    return response_resp(message="更新知识库成功")


@router.post(
    "/{dataset_id}/delete",
    response_model=ResponseBase,
    summary="4.4 删除指定的知识库",
    description="用于删除指定的知识库，删除知识库后，在后端会将关联的应用配置、知识库下的所有文档/文档片段/查询语句也进行一并删除（该接口为耗时接口，将使用异步/消息队列的形式来实现），删除后以前关联的应用将无法引用该知识库。",
)
async def delete_dataset(
    current_user: CurrentUser,
    db: SessionDB,
    dataset_id: str,
):
    """用于删除指定的知识库，删除知识库后，在后端会将关联的应用配置、知识库下的所有文档/文档片段/查询语句也进行一并删除（该接口为耗时接口，将使用异步/消息队列的形式来实现），删除后以前关联的应用将无法引用该知识库。"""
    await DatasetService.delete_dataset(
        db,
        current_user,
        dataset_id
    )
    return response_resp(message="删除知识库成功")


@router.get(
    "/{dataset_id}",
    response_model=ResponseBase,
    summary="4.5 获取指定的知识库详情",
    description="用于获取指定的知识库详情信息。",
)
async def get_dataset_detail(
    current_user: CurrentUser,
    db: SessionDB,
    dataset_id: str,
):
    """用于获取指定的知识库详情信息。"""
    result = await DatasetService.get_dataset_detail(
        db,
        current_user,
        dataset_id
    )
    return response_resp(data=result, message="获取知识库详情成功")