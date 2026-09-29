from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.orm import Session
from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.transaction import transaction
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.repositories.booking_repository import BookingRepository
from app.services.booking_service import BookingService

logger = logging.getLogger("cleanup_tasks")

ABANDONED_THRESHOLD_MINUTES = 15


def expire_abandoned_bookings_in_session(
    db: Session, threshold_minutes: int = ABANDONED_THRESHOLD_MINUTES
) -> dict:
    # Cancels PENDING bookings nobody ever paid for and frees the seat.
    # Skips anything with a live payment (PENDING or SUCCESS) - don't want to
    # cancel underneath a payment that's mid-flight, same problem as a late webhook.
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)
    candidate_ids = [
        str(row.id)
        for row in db.query(Booking.id).filter(
            Booking.status == BookingStatus.PENDING,
            Booking.created_at < cutoff,
        ).all()
    ]

    bookings = BookingRepository(db)
    service = BookingService(db)
    expired = 0

    for booking_id in candidate_ids:
        cancelled = False
        try:
            with transaction(db):
                booking = bookings.get_for_update(booking_id)
                if not booking or booking.status != BookingStatus.PENDING:
                    continue

                has_live_payment = db.query(Payment.id).filter(
                    Payment.booking_id == booking.id,
                    Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.SUCCESS]),
                ).first() is not None
                if has_live_payment:
                    continue

                service.transition(booking, BookingStatus.CANCELLED, "system_cleanup")
                cancelled = True
        except Exception:
            logger.exception(f"Failed to expire abandoned booking {booking_id}")
            continue

        if cancelled:
            expired += 1
            logger.info(f"Expired abandoned booking {booking_id}, seat released")

    return {"candidates": len(candidate_ids), "expired": expired}


@celery_app.task
def expire_abandoned_bookings():
    db = SessionLocal()
    try:
        return expire_abandoned_bookings_in_session(db)
    finally:
        db.close()