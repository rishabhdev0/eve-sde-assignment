import uuid
from decimal import Decimal
from pydantic import BaseModel, Field


class CentreTestCreate(BaseModel):
    test_id: uuid.UUID
    price: Decimal = Field(gt=0)
    turnaround_hours: int = Field(gt=0, default=24)


class CentreTestOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    test_name: str
    price: Decimal
    turnaround_hours: int

    class Config:
        from_attributes = True