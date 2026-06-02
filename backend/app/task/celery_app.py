from os import name
from celery import Celery
from config import settings

celery_app = Celery("llmops")

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    broker=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_URL,
    enable_utc=True,
    timezone="Asia/Shanghai",
    broker_connection_retry_on_startup=True,
    worker_heartbeat=600,
    broker_transport_options={
        "health_check_interval": 30,  # 每隔5秒检查一次连接
        "max_retries": 10,  # 最大重试次数
        "socket_keepalive": True,  # 启用TCP保活机制
    }
)

celery_app.autodiscover_tasks(["app.task"])