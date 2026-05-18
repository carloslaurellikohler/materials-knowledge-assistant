from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "mka",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.task_default_queue = "mka-default"

