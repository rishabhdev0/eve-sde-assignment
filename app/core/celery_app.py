from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "eve_backend",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.payment_tasks",
        "app.tasks.reconciliation_tasks",
        "app.tasks.cleanup_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "reconcile-stuck-payments": {
        "task": "app.tasks.reconciliation_tasks.reconcile_stuck_payments",
        "schedule": 300.0,
    },
    "expire-abandoned-bookings": {
        "task": "app.tasks.cleanup_tasks.expire_abandoned_bookings",
        "schedule": 300.0,
    },
}

celery = celery_app  # alias so `-A app.core.celery_app` auto-discovers it