from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.api.deps import get_current_user
from app.schemas.booking import BookingCreate, BookingOut
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return BookingService(db).create_booking(str(user.id), str(payload.slot_id))


@router.get("/", response_model=list[BookingOut])
def list_my_bookings(skip: int = 0, limit: int = 20, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return BookingService(db).list_my_bookings(str(user.id), skip=skip, limit=limit)


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return BookingService(db).get_booking(booking_id, str(user.id))


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return BookingService(db).cancel_booking(booking_id, str(user.id))