from sqlalchemy.orm import Session
from app.repositories.webhook_repository import WebhookRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.booking_repository import BookingRepository
from app.models.payment import Payment, PaymentStatus
from app.models.payment_event import PaymentEvent
from app.models.booking import BookingStatus
from app.schemas.webhook import WebhookEventPayload, WebhookPaymentStatus
from app.services.booking_service import BookingService
from app.core.redis_client import redis_client
from app.db.transaction import transaction
from app.core.exceptions import AppException
import logging

logger = logging.getLogger("webhook_service")

TERMINAL_BOOKING_STATUSES = {BookingStatus.CANCELLED, BookingStatus.FAILED}


class WebhookPaymentNotFoundError(AppException):
    status_code = 404
    detail = "Payment referenced by webhook not found"


class WebhookBookingNotFoundError(AppException):
    status_code = 404
    detail = "Booking referenced by webhook not found"


class WebhookService:
    def __init__(self, db: Session):
        self.db = db
        self.webhooks = WebhookRepository(db)
        self.payments = PaymentRepository(db)
        self.bookings = BookingRepository(db)
        self.booking_service = BookingService(db)

    def handle_event(self, payload: WebhookEventPayload) -> dict:
        redis_key = f"webhook_processed:{payload.event_id}"
        if redis_client.exists(redis_key):
            logger.info(f"Duplicate webhook event {payload.event_id} - Redis pre-check hit, no-op")
            return {"status": "duplicate_ignored", "event_id": payload.event_id}

        with transaction(self.db):
            existing = self.webhooks.get_by_event_id(payload.event_id)
            if existing:
                logger.info(f"Duplicate webhook event {payload.event_id} - DB check hit, no-op")
                return {"status": "duplicate_ignored", "event_id": payload.event_id}

            self.webhooks.create(payload.event_id, payload.model_dump_json())

            booking = self.bookings.get_for_update(payload.booking_id)
            if not booking:
                raise WebhookBookingNotFoundError()

            payment = self.payments.get_for_update(payload.payment_id)
            if not payment:
                raise WebhookPaymentNotFoundError()

            if payment.status != PaymentStatus.PENDING:
                logger.info(f"Payment {payment.id} already in state {payment.status}, ignoring event {payload.event_id}")
                result = {"status": "already_resolved", "event_id": payload.event_id}
            elif booking.status in TERMINAL_BOOKING_STATUSES:
                # Booking got cancelled/failed while this payment was still in flight.
                # Can't let transition() raise here - that'd roll back the dedup record
                # too and the payment would stay stuck PENDING forever on every retry.
                result = self._resolve_against_terminal_booking(booking, payment, payload)
            else:
                result = self._resolve_normally(booking, payment, payload)

        # Only mark it processed in Redis once the DB transaction actually commits.
        redis_client.setex(redis_key, 86400, "1")
        return result

    def _resolve_normally(self, booking, payment: Payment, payload: WebhookEventPayload) -> dict:
        payment.provider_ref = payload.provider_ref
        if payload.status == WebhookPaymentStatus.SUCCESS:
            payment.status = PaymentStatus.SUCCESS
            self.db.add(PaymentEvent(payment_id=payment.id, status="SUCCESS", note="Confirmed via webhook"))
            self.booking_service.transition(booking, BookingStatus.CONFIRMED, "payment_webhook")
        else:
            payment.status = PaymentStatus.FAILED
            self.db.add(PaymentEvent(payment_id=payment.id, status="FAILED", note="Failed via webhook"))
            self.booking_service.transition(booking, BookingStatus.FAILED, "payment_webhook")
        return {"status": "processed", "event_id": payload.event_id, "payment_status": payload.status.value}

    def _resolve_against_terminal_booking(self, booking, payment: Payment, payload: WebhookEventPayload) -> dict:
        payment.provider_ref = payload.provider_ref

        if payload.status == WebhookPaymentStatus.FAILED:
            payment.status = PaymentStatus.FAILED
            self.db.add(PaymentEvent(
                payment_id=payment.id, status="FAILED",
                note=f"Failed via webhook, booking already {booking.status.value}",
            ))
            return {"status": "processed_terminal_booking", "event_id": payload.event_id}

        # Money got captured for a booking that's no longer valid. Record the
        # success honestly, refund it right away, and log it loud for someone to see.
        logger.warning(
            f"Payment {payment.id} succeeded but booking {booking.id} was already "
            f"{booking.status.value} - issuing automatic refund"
        )
        payment.status = PaymentStatus.SUCCESS
        self.db.add(PaymentEvent(
            payment_id=payment.id, status="SUCCESS",
            note=f"Succeeded via webhook, but booking already {booking.status.value} - refunding",
        ))

        refund = Payment(
            booking_id=booking.id,
            amount=payment.amount,
            status=PaymentStatus.REFUNDED,
            provider_ref=f"AUTO-REFUND-OF-{payment.provider_ref}",
            refunded_payment_id=payment.id,
        )
        self.db.add(refund)
        self.db.flush()
        self.db.add(PaymentEvent(
            payment_id=refund.id, status="REFUNDED",
            note=f"Auto-refunded - payment succeeded after booking was already {booking.status.value}",
        ))
        return {"status": "processed_with_auto_refund", "event_id": payload.event_id}