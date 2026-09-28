import uuid
from pydantic import BaseModel


class TestCreate(BaseModel):
    name: str
    description: str | None = None


class TestOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None

    class Config:
        from_attributes = True