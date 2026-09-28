from sqlalchemy.orm import Session
from app.models.webhook_event import WebhookEvent


class WebhookRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_event_id(self, event_id: str) -> WebhookEvent | None:
        return self.db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()

    def create(self, event_id: str, payload: str) -> WebhookEvent:
        event = WebhookEvent(event_id=event_id, payload=payload)
        self.db.add(event)
        self.db.flush()
        return event