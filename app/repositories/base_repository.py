from typing import TypeVar, Generic, Type
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    def __init__(self, db: Session, model: Type[ModelType]):
        self.db = db
        self.model = model

    def get_by_id(self, id_: str) -> ModelType | None:
        return self.db.query(self.model).filter(self.model.id == id_).first()

    def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def list(self, skip: int = 0, limit: int = 50) -> list[ModelType]:
        return self.db.query(self.model).offset(skip).limit(limit).all()