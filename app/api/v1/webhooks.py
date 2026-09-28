from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.webhook import WebhookEventPayload
from app.services.webhook_service import WebhookService
from app.core.config import settings

router = APIRouter(prefix="/payments", tags=["webhooks"])


def verify_webhook_secret(x_webhook_secret: str = Header(...)):
    """
    Simulated provider authentication. A real payment provider (Stripe, Razorpay, etc.)
    signs each webhook with HMAC using a secret only the two parties share, so the
    receiver can verify the request genuinely came from the provider and wasn't
    forged by a third party who merely guessed a valid payment_id.

    This uses a simple shared-secret header comparison rather than full HMAC signing,
    since there's no real external provider here to establish a signing scheme with -
    documented as a known simplification in the README, not silently skipped.
    """
    if x_webhook_secret != settings.WEBHOOK_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook credentials")


@router.post("/webhook/", dependencies=[Depends(verify_webhook_secret)])
def payment_webhook(payload: WebhookEventPayload, db: Session = Depends(get_db)):
    return WebhookService(db).handle_event(payload)