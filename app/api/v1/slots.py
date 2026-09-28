from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.schemas.slot import SlotCreate, SlotOut
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/slots", tags=["slots"])


@router.post("/", response_model=SlotOut, status_code=status.HTTP_201_CREATED)
def create_slot(payload: SlotCreate, db: Session = Depends(get_db), _=Depends(get_current_user)):
    slot = CatalogService(db).create_slot(
        str(payload.centre_test_id), payload.start_time, payload.end_time, payload.capacity
    )
    return SlotOut(
        id=slot.id, centre_test_id=slot.centre_test_id, start_time=slot.start_time,
        end_time=slot.end_time, capacity=slot.capacity, booked_count=slot.booked_count,
        is_available=slot.is_available,
    )


@router.get("/", response_model=list[SlotOut])
def list_available_slots(centre_test_id: str, db: Session = Depends(get_db)):
    slots = CatalogService(db).list_available_slots(centre_test_id)
    return [
        SlotOut(id=s.id, centre_test_id=s.centre_test_id, start_time=s.start_time, end_time=s.end_time,
                capacity=s.capacity, booked_count=s.booked_count, is_available=s.is_available)
        for s in slots
    ]