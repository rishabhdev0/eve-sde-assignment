from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.webhook import WebhookEventPayload
from app.services.webhook_service import WebhookService
from app.core.config import settings

router = APIRouter(prefix="/payments", tags=["webhooks"])


def verify_webhook_secret(x_webhook_secret: str = Header(...)):
    # Just a shared secret, not real HMAC signing - no actual provider to set that up with.
    # Called out in the README as a known shortcut, not something we missed.
    if x_webhook_secret != settings.WEBHOOK_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook credentials")


@router.post("/webhook/", dependencies=[Depends(verify_webhook_secret)])
def payment_webhook(payload: WebhookEventPayload, db: Session = Depends(get_db)):
    return WebhookService(db).handle_event(payload)