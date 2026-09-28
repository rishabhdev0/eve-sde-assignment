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
    """
    Finds payments stuck in PENDING past a reasonable window - meaning the async
    worker never got to them, or crashed mid-task without retrying successfully.

    Real-world note: a production system would query the actual payment provider's
    API here to find out the true status before deciding anything (the payment may
    have genuinely succeeded on their end even if our webhook never arrived). Since
    this assignment simulates the provider with no real external state to check,
    the safest fallback is to mark it FAILED rather than leave it stuck forever -
    a failed booking can be retried by the user; a booking silently stuck in limbo
    cannot.

    Routes through the same WebhookService.handle_event() path as every other
    state change, so the existing idempotency/locking guarantees still apply here -
    this is a fallback trigger, not a separate way to mutate state.
    """
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