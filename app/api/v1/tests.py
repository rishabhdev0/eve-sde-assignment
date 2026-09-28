from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.schemas.test import TestCreate, TestOut
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/tests", tags=["tests"])


@router.post("/", response_model=TestOut, status_code=status.HTTP_201_CREATED)
def create_test(payload: TestCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return CatalogService(db).create_test(payload.name, payload.description)


@router.get("/", response_model=list[TestOut])
def list_tests(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return CatalogService(db).list_tests(skip=skip, limit=limit)