from app.core.celery_app import celery_app
from app.db.session import SessionLocal
import logging

logger = logging.getLogger("payment_tasks")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def process_payment_async(self, payment_id: str):
    db = SessionLocal()
    try:
        from app.services.payment_service import PaymentService
        PaymentService(db).simulate_processing(payment_id)
    except Exception as exc:
        logger.exception(f"Payment processing failed for {payment_id}, retrying")
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()