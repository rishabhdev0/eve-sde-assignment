import uuid
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel
from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    slot_id: uuid.UUID


class BookingOut(BaseModel):
    id: uuid.UUID
    slot_id: uuid.UUID
    centre_test_id: uuid.UUID
    amount: Decimal
    status: BookingStatus
    created_at: datetime

    class Config:
        from_attributes = True