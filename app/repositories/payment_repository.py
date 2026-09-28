from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.payment import Payment


class PaymentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.flush()
        return payment

    def get_by_id(self, payment_id: str) -> Payment | None:
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_for_update(self, payment_id: str) -> Payment | None:
        stmt = select(Payment).where(Payment.id == payment_id).with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_booking(self, booking_id: str) -> list[Payment]:
        return self.db.query(Payment).filter(Payment.booking_id == booking_id).order_by(Payment.created_at.desc()).all()