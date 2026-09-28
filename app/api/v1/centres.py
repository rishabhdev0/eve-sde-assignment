from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.schemas.centre import CentreCreate, CentreOut
from app.schemas.centre_test import CentreTestCreate, CentreTestOut
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/centres", tags=["centres"])


@router.post("/", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
def create_centre(payload: CentreCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return CatalogService(db).create_centre(payload.name, payload.location)


@router.get("/", response_model=list[CentreOut])
def list_centres(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return CatalogService(db).list_centres(skip=skip, limit=limit)


@router.get("/{centre_id}", response_model=CentreOut)
def get_centre(centre_id: str, db: Session = Depends(get_db)):
    return CatalogService(db).get_centre(centre_id)


@router.post("/{centre_id}/tests", response_model=CentreTestOut, status_code=status.HTTP_201_CREATED)
def add_test_to_centre(centre_id: str, payload: CentreTestCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    offering = CatalogService(db).add_test_to_centre(
        centre_id, str(payload.test_id), payload.price, payload.turnaround_hours
    )
    return CentreTestOut(
        id=offering.id, test_id=offering.test_id, test_name=offering.test.name,
        price=offering.price, turnaround_hours=offering.turnaround_hours,
    )


@router.get("/{centre_id}/tests", response_model=list[CentreTestOut])
def list_tests_for_centre(centre_id: str, db: Session = Depends(get_db)):
    offerings = CatalogService(db).list_tests_for_centre(centre_id)
    return [
        CentreTestOut(id=o.id, test_id=o.test_id, test_name=o.test.name, price=o.price, turnaround_hours=o.turnaround_hours)
        for o in offerings
    ]