from enum import Enum
from pydantic import BaseModel, field_validator


class WebhookPaymentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class WebhookEventPayload(BaseModel):
    event_id: str
    booking_id: str
    payment_id: str
    status: WebhookPaymentStatus
    provider_ref: str | None = None

    @field_validator("event_id", "booking_id", "payment_id")
    @classmethod
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v