import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, field_validator


class SlotCreate(BaseModel):
    centre_test_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    capacity: int = 1

    @field_validator("start_time")
    @classmethod
    def start_time_not_in_past(cls, v: datetime):
        now = datetime.now(timezone.utc)
        # normalize naive datetimes to UTC for comparison - Pydantic accepts both
        compare_v = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if compare_v < now:
            raise ValueError("start_time cannot be in the past")
        return v

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v, info):
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("end_time must be after start_time")
        return v

    @field_validator("capacity")
    @classmethod
    def capacity_positive(cls, v):
        if v < 1:
            raise ValueError("capacity must be at least 1")
        return v


class SlotOut(BaseModel):
    id: uuid.UUID
    centre_test_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    capacity: int
    booked_count: int
    is_available: bool

    class Config:
        from_attributes = True