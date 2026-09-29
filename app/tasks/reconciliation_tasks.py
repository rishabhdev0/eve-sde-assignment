import uuid
from datetime import datetime, timedelta, timezone
from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.payment import Payment, PaymentStatus
from app.schemas.webhook import WebhookEventPayload, WebhookPaymentStatus
import logging

logger = logging.getLogger("reconciliation_tasks")

STUCK_THRESHOLD_MINUTES = 10


@celery_app.task
def reconcile_stuck_payments():
    # Catches payments stuck in PENDING too long - worker never picked it up,
    # or crashed before finishing. A real system would check the provider's API
    # first, but there's no real provider here, so we just fail it - better than
    # leaving it stuck forever, and the user can retry.
    # Goes through the normal webhook handler so it gets the same locking and
    # dedup guarantees as everything else, not some separate shortcut.
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
        stuck = db.query(Payment).filter(
            Payment.status == PaymentStatus.PENDING,
            Payment.created_at < cutoff,
        ).all()

        from app.services.webhook_service import WebhookService

        recovered = 0
        for payment in stuck:
            logger.warning(f"Payment {payment.id} stuck in PENDING since {payment.created_at} - auto-failing")
            payload = WebhookEventPayload(
                event_id=f"reconciliation-timeout-{payment.id}-{uuid.uuid4()}",
                booking_id=str(payment.booking_id),
                payment_id=str(payment.id),
                status=WebhookPaymentStatus.FAILED,
                provider_ref="RECONCILIATION-TIMEOUT",
            )
            try:
                WebhookService(db).handle_event(payload)
                recovered += 1
            except Exception:
                logger.exception(f"Failed to auto-resolve stuck payment {payment.id}")

        return {"stuck_count": len(stuck), "recovered_count": recovered}
    finally:
        db.close()