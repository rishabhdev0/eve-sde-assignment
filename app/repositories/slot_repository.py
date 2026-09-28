from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.slot import Slot


class SlotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, slot: Slot) -> Slot:
        self.db.add(slot)
        self.db.commit()
        self.db.refresh(slot)
        return slot

    def get_by_id(self, slot_id: str) -> Slot | None:
        return self.db.query(Slot).filter(Slot.id == slot_id).first()

    def get_for_update(self, slot_id: str) -> Slot | None:
        """Row-locks the slot until the enclosing transaction commits/rolls back.
        Prevents two concurrent bookings from both passing the capacity check."""
        stmt = select(Slot).where(Slot.id == slot_id).with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def list_available_for_centre_test(self, centre_test_id: str) -> list[Slot]:
        return (
            self.db.query(Slot)
            .filter(Slot.centre_test_id == centre_test_id, Slot.booked_count < Slot.capacity)
            .order_by(Slot.start_time)
            .all()
        )

    def find_existing(self, centre_test_id: str, start_time) -> Slot | None:
        return (
            self.db.query(Slot)
            .filter(Slot.centre_test_id == centre_test_id, Slot.start_time == start_time)
            .first()
        )