#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""智能体队列管理器（迁移自 imooc agent_queue_manager.py）。

适配 FastAPI 后端：Redis 客户端由外部注入（同步客户端，因 Agent 在子线程中运行）。
decode_responses=True，故 get 返回 str，无需 decode。
"""
from __future__ import annotations

import queue
import time
import uuid
from queue import Queue
from typing import Generator
from uuid import UUID

from redis import Redis

from app.core.agent.entities.queue_entity import AgentThought, QueueEvent
from app.entities.conversation_entity import InvokeFrom


class AgentQueueManager:
    """智能体队列管理器"""
    user_id: UUID
    invoke_from: InvokeFrom
    redis_client: Redis
    _queues: dict[str, Queue]

    def __init__(
        self,
        user_id: UUID,
        invoke_from: InvokeFrom,
        redis_client: Redis,
    ) -> None:
        """构造函数，初始化智能体队列管理器"""
        self.user_id = user_id
        self.invoke_from = invoke_from
        self.redis_client = redis_client
        self._queues = {}

    def listen(self, task_id: UUID) -> Generator:
        """监听队列返回的生成式数据"""
        # 1.定义基础数据记录超时时间、开始时间、最后一次ping通时间
        listen_timeout = 600
        start_time = time.time()
        last_ping_time = 0

        # 2.创建循环队列执行死循环读取数据，直到超时或者数据读取完毕
        while True:
            try:
                # 3.从队列中提取数据并检测数据是否存在，如果存在则使用yield关键字返回
                item = self.queue(task_id).get(timeout=1)
                if item is None:
                    break
                yield item
            except queue.Empty:
                continue
            finally:
                # 4.计算获取数据的总耗时
                elapsed_time = time.time() - start_time

                # 5.每10秒发起一个ping请求
                if elapsed_time // 10 > last_ping_time:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.PING,
                    ))
                    last_ping_time = elapsed_time // 10

                # 6.判断总耗时是否超时，如果超时则往队列中添加超时事件
                if elapsed_time >= listen_timeout:
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.TIMEOUT,
                    ))

                # 7.检测是否停止，如果已经停止则添加停止事件
                if self._is_stopped(task_id):
                    self.publish(task_id, AgentThought(
                        id=uuid.uuid4(),
                        task_id=task_id,
                        event=QueueEvent.STOP,
                    ))

    def stop_listen(self, task_id: UUID) -> None:
        """停止监听队列信息"""
        self.queue(task_id).put(None)

    def publish(self, task_id: UUID, agent_thought: AgentThought) -> None:
        """发布事件信息到队列"""
        # 1.将事件添加到队列中
        self.queue(task_id).put(agent_thought)

        # 2.检测事件类型是否为需要停止的类型，涵盖STOP、ERROR、TIMEOUT、AGENT_END
        if agent_thought.event in [QueueEvent.STOP, QueueEvent.ERROR, QueueEvent.TIMEOUT, QueueEvent.AGENT_END]:
            self.stop_listen(task_id)

    def publish_error(self, task_id: UUID, error) -> None:
        """发布错误信息到队列"""
        self.publish(task_id, AgentThought(
            id=uuid.uuid4(),
            task_id=task_id,
            event=QueueEvent.ERROR,
            observation=str(error),
        ))

    def _is_stopped(self, task_id: UUID) -> bool:
        """检测任务是否停止"""
        task_stopped_cache_key = self.generate_task_stopped_cache_key(task_id)
        result = self.redis_client.get(task_stopped_cache_key)
        return result is not None

    def queue(self, task_id: UUID) -> Queue:
        """根据传递的task_id获取对应的任务队列信息"""
        # 1.从队列字典中获取对应的任务队列
        q = self._queues.get(str(task_id))

        # 2.检测队列是否存在，如果不存在则创建队列，并添加缓存键标识
        if not q:
            # 3.添加缓存键标识
            user_prefix = "account" if self.invoke_from in [
                InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER, InvokeFrom.ASSISTANT_AGENT,
            ] else "end-user"

            # 4.设置任务对应的缓存键，代表这次任务已经开始了
            self.redis_client.setex(
                self.generate_task_belong_cache_key(task_id),
                1800,
                f"{user_prefix}-{str(self.user_id)}",
            )

            # 5.将任务队列添加到队列字典中
            q = Queue()
            self._queues[str(task_id)] = q

        return q

    @classmethod
    def set_stop_flag(
        cls,
        task_id: UUID,
        invoke_from: InvokeFrom,
        user_id: UUID,
        redis_client: Redis,
    ) -> None:
        """根据传递的任务id+调用来源停止某次会话"""
        # 1.获取当前任务的缓存键，如果任务没执行，则不需要停止
        result = redis_client.get(cls.generate_task_belong_cache_key(task_id))
        if not result:
            return

        # 2.计算对应缓存键的结果
        user_prefix = "account" if invoke_from in [
            InvokeFrom.WEB_APP, InvokeFrom.DEBUGGER, InvokeFrom.ASSISTANT_AGENT,
        ] else "end-user"
        # decode_responses=True 时 result 为 str
        if result != f"{user_prefix}-{str(user_id)}":
            return

        # 3.生成停止键标识
        stopped_cache_key = cls.generate_task_stopped_cache_key(task_id)
        redis_client.setex(stopped_cache_key, 600, 1)

    @classmethod
    def generate_task_belong_cache_key(cls, task_id: UUID) -> str:
        """生成任务专属的缓存键"""
        return f"generate_task_belong:{str(task_id)}"

    @classmethod
    def generate_task_stopped_cache_key(cls, task_id: UUID) -> str:
        """生成任务已停止的缓存键"""
        return f"generate_task_stopped:{str(task_id)}"
