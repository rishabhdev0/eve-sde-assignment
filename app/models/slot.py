import uuid
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class Slot(Base):
    """A bookable time window for a given centre+test. capacity/booked_count prevents double-booking."""
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("centre_test_id", "start_time", name="uq_slot_time"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    centre_test_id = Column(UUID(as_uuid=True), ForeignKey("centre_tests.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    capacity = Column(Integer, nullable=False, default=1)
    booked_count = Column(Integer, nullable=False, default=0)

    @property
    def is_available(self) -> bool:
        return self.booked_count < self.capacity