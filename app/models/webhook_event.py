import uuid
from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class WebhookEvent(Base):
    # Dedup log only - has this event_id been seen before, nothing else.
    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String, unique=True, nullable=False, index=True)
    payload = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())