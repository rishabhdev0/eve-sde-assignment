import uuid
from pydantic import BaseModel


class CentreCreate(BaseModel):
    name: str
    location: str


class CentreOut(BaseModel):
    id: uuid.UUID
    name: str
    location: str

    class Config:
        from_attributes = True