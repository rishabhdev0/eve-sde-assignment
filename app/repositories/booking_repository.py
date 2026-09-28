from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.booking import Booking


class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, booking: Booking) -> Booking:
        self.db.add(booking)
        self.db.flush()  # get the id without committing - caller controls the transaction
        return booking

    def get_by_id(self, booking_id: str) -> Booking | None:
        return self.db.query(Booking).filter(Booking.id == booking_id).first()

    def get_for_update(self, booking_id: str) -> Booking | None:
        stmt = select(Booking).where(Booking.id == booking_id).with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> list[Booking]:
        return (
            self.db.query(Booking)
            .filter(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
            .offset(skip).limit(limit)
            .all()
        )

    def get_active_booking_for_user_slot(self, user_id: str, slot_id: str) -> Booking | None:
        from app.models.booking import BookingStatus
        return (
            self.db.query(Booking)
            .filter(
                Booking.user_id == user_id,
                Booking.slot_id == slot_id,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
            )
            .first()
        )