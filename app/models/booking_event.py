import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class BookingEvent(Base):
    """Audit log: every status transition a booking goes through, and what triggered it."""
    __tablename__ = "booking_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False, index=True)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    triggered_by = Column(String, nullable=False)  # e.g. "user", "payment_webhook", "system"
    created_at = Column(DateTime(timezone=True), server_default=func.now())