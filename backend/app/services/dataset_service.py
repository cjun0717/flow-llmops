
import uuid
from typing import Optional, Tuple
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import HTTPException
from models import Account, Dataset, Document, AppDatasetJoin
from entity.dataset_entity import DEFAULT_DATASET_DESCRIPTION_FORMATTER
from schemas.dataset import DatasetInfo
from schemas.response import PageInfo, Page
from task.dataset_task import delete_dataset
class DatasetService:


    @classmethod
    async def get_datasets_with_page(
        cls, 
        db: AsyncSession,
        account: Account,
        search_word: Optional[str] = None,
        current_page: int = 1,
        page_size: int = 10,
    ) -> PageInfo[DatasetInfo]:
        """用于获取当前登录账号的知识库列表信息，该接口支持搜索+分页，传递搜索词为空时代表不搜索。"""
        # 构建基础查询条件
        conditions = [Dataset.account_id == account.id]
        if search_word:
            conditions.append(Dataset.name.ilike(f"%{search_word}%"))
        
        # 查询总数
        count_query = select(func.count(Dataset.id)).where(*conditions)
        total = await db.scalar(count_query) or 0
        
        # 查询知识库数据
        offset = (current_page - 1) * page_size
        query = (
            select(Dataset)
            .where(*conditions)
            .order_by(Dataset.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        datasets = await db.execute(query).scalars().all()
        
        if not datasets:
            result = PageInfo[DatasetInfo](
                list=[],
                paginator=Page(
                    total_page=0,
                    total_record=total,
                    current_page=current_page,
                    page_size=page_size
                )
            )
            return result
        
        dataset_ids = [d.id for d in datasets]
        
        # 批量查询文档统计信息
        doc_stats_query = (
            select(
                Document.dataset_id,
                func.count(Document.id).label("document_count"),
                func.coalesce(func.sum(Document.character_count), 0).label("character_count")
            )
            .where(Document.dataset_id.in_(dataset_ids))
            .group_by(Document.dataset_id)
        )
        doc_stats_result = await db.execute(doc_stats_query)
        doc_stats = {
            row.dataset_id: {"document_count": row.document_count, "character_count": row.character_count}
            for row in doc_stats_result
        }
        
        # 批量查询关联app数量
        app_stats_query = (
            select(
                AppDatasetJoin.dataset_id,
                func.coalesce(func.count(AppDatasetJoin.id), 0).label("related_app_count")
            )
            .where(AppDatasetJoin.dataset_id.in_(dataset_ids))
            .group_by(AppDatasetJoin.dataset_id)
        )
        app_stats_result = await db.execute(app_stats_query)
        app_stats = {
            row.dataset_id: row.related_app_count
            for row in app_stats_result
        }
        
        # 组装数据
        dataset_list = []
        for dataset in datasets:
            stats = doc_stats.get(dataset.id, {"document_count": 0, "character_count": 0})
            dataset_list.append(DatasetInfo(
                id=dataset.id,
                name=dataset.name,
                icon=dataset.icon,
                description=dataset.description,
                document_count=stats["document_count"],
                character_count=stats["character_count"],
                related_app_count=app_stats.get(dataset.id, 0),
                updated_at=int(dataset.updated_at.timestamp()),
                created_at=int(dataset.created_at.timestamp()),
            ))
        
        # 构造分页信息
        total_page = (total + page_size - 1) // page_size
        result = PageInfo[DatasetInfo](
            list=dataset_list,
            paginator=Page(
                total_page=total_page,
                total_record=total,
                current_page=current_page,
                page_size=page_size
            )
        )
        return result
    
    @classmethod
    async def create_dataset(cls, db:AsyncSession, account: Account, data: dict):
        """创建知识库"""
        # 检测是否存在相同名称的知识库
        dataset = await db.execute(select(Dataset).where(
            Dataset.account_id == account.id,
            Dataset.name == data["name"]
        )).one_or_none()
        if dataset:
            raise HTTPException(status_code=400, detail=f"知识库{data['name']}已存在")

        # 2 检测是否传递了知识库描述信息
        if not data.get("description"):
            data["description"] = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(name=data["name"])
        
        # 创建知识库
        dataset = Dataset(
            id=uuid.uuid4(),
            account_id=account.id,
            name=data["name"],
            icon=data["icon"],
            description=data["description"],
        )
        await db.add(dataset)
        await db.commit()

    
    @classmethod
    async def update_dataset(
        cls, 
        db: AsyncSession,
        account: Account,
        dataset_id: str,
        dataset_info: dict,
    ):
        """更新知识库"""
        # 检测知识库是否存在
        dataset = await db.execute(select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.account_id == account.id
        )).one_or_none()
        if not dataset:
            raise HTTPException(status_code=404, detail=f"知识库{dataset_id}不存在")
        
        # 检测修改后的知识库名称是否出现重名
        check_data = await db.execute(select(Dataset).where(
            Dataset.account_id == account.id,
            Dataset.id != dataset_id,
            Dataset.name == dataset_info.get("name")
        )).one_or_none()
        if check_data:
            raise HTTPException(status_code=400, detail=f"知识库{dataset_info.get('name')}已存在")
        
        # 更新知识库信息
        dataset.name = dataset_info.get("name")
        dataset.icon = dataset_info.get("icon")
        dataset.description = dataset_info.get("description")
        await db.commit()
        return dataset

    @classmethod
    async def delete_dataset(
        cls, 
        db: AsyncSession,
        account: Account,
        dataset_id: str,
    ):
        """删除知识库"""
        # 检测知识库是否存在
        dataset = await db.execute(select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.account_id == account.id
        )).one_or_none()
        if not dataset:
            raise HTTPException(status_code=404, detail=f"知识库{dataset_id}不存在")
        
        try:
            # 删除关联的应用配置
            await db.execute(
                delete(AppDatasetJoin).where(AppDatasetJoin.dataset_id == dataset_id)
            )
            # 删除知识库
            await db.delete(dataset)
            await db.commit()

            # 调用异步任务执行后续操作
            delete_dataset.apply_async(args=[uuid.UUID(dataset_id)])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除知识库失败,请稍后重试,{str(e)}")
       
   
    @classmethod
    async def get_dataset_detail(
        cls, 
        db: AsyncSession,
        account: Account,
        dataset_id: str,
    ):
        """获取知识库详情"""
        # 检测知识库是否存在
        dataset = await db.execute(select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.account_id == account.id
        )).one_or_none()
        if not dataset:
            raise HTTPException(status_code=404, detail=f"知识库{dataset_id}不存在")
        
        # 组装数据
        return DatasetInfo(
            id=dataset.id,
            name=dataset.name,
            icon=dataset.icon,
            description=dataset.description,
            document_at=int(dataset.updated_at.timestamp()),
            created_at=int(dataset.created_at.timestamp()),
        )