#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工作流节点同步 DB 访问辅助。

工作流引擎在子线程中同步执行，节点构造/执行时需要访问数据库。
通过 ``run_sync`` 在子线程中用 ``asyncio.run`` 运行协程（子线程无运行事件循环，
可安全创建新循环）。若意外在事件循环线程中调用，则回退到线程池兜底。
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, TypeVar

T = TypeVar("T")


def run_sync(coro: Awaitable[T]) -> T:
    """在同步上下文中运行异步协程并返回结果。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # 已在事件循环线程中调用，回退到独立线程运行
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(coro))
        return future.result()
