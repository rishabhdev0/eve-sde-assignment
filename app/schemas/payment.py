import uuid
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel
from app.models.payment import PaymentStatus


class PaymentCreate(BaseModel):
    booking_id: uuid.UUID


class PaymentOut(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    amount: Decimal
    status: PaymentStatus
    created_at: datetime

    class Config:
        from_attributes = True