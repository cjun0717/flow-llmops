#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
from celery_app import celery_app
from models import Segment, Document, KeywordTable, DatasetQuery
from sqlalchemy import delete
from config.database import AsyncSessionLocal
import uuid

async def _delete_dataset_async(dataset_id: uuid.UUID):
    """异步删除知识库的内部函数"""
    async with AsyncSessionLocal() as db:
        try:
            # 删除关联的文档记录
            await db.execute(delete(Document).where(Document.dataset_id == dataset_id))
            
            # 删除关联的片段记录
            await db.execute(delete(Segment).where(Segment.dataset_id == dataset_id))

            # 删除关联的关键词记录
            await db.execute(delete(KeywordTable).where(KeywordTable.dataset_id == dataset_id))
            
            # 删除关联的查询记录
            await db.execute(delete(DatasetQuery).where(DatasetQuery.dataset_id == dataset_id))
            
            # 提交事务
            await db.commit()
        except Exception:
            await db.rollback()
        finally:
            await db.close()
    # 5.调用向量数据库删除知识库的关联记录
    # TODO: 实现删除向量数据库的逻辑
    # 直接使用langchain封装的删除

@celery_app.task(name="delete_dataset_task")
def delete_dataset(dataset_id: uuid.UUID):
    """删除知识库任务（Celery 任务入口）"""
    asyncio.run(_delete_dataset_async(dataset_id))
