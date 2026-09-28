import random
import uuid
from sqlalchemy.orm import Session
from app.repositories.payment_repository import PaymentRepository
from app.repositories.booking_repository import BookingRepository
from app.models.payment import Payment, PaymentStatus
from app.models.payment_event import PaymentEvent
from app.models.booking import BookingStatus
from app.db.transaction import transaction
from app.core.exceptions import AppException
from app.schemas.webhook import WebhookEventPayload, WebhookPaymentStatus


class BookingNotFoundForPaymentError(AppException):
    status_code = 404
    detail = "Booking not found"


class ForbiddenPaymentAccessError(AppException):
    status_code = 403
    detail = "You do not have access to this booking"


class BookingNotPayableError(AppException):
    status_code = 400
    detail = "This booking is not in a payable state"


class DuplicateActivePaymentError(AppException):
    status_code = 400
    detail = "An active payment already exists for this booking"


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.payments = PaymentRepository(db)
        self.bookings = BookingRepository(db)

    def create_payment(self, user_id: str, booking_id: str) -> Payment:
        # Ownership/existence check first, outside the lock - no point locking a row
        # the caller isn't even allowed to touch.
        booking = self.bookings.get_by_id(booking_id)
        if not booking:
            raise BookingNotFoundForPaymentError()
        if str(booking.user_id) != str(user_id):
            raise ForbiddenPaymentAccessError()

        payment = None
        with transaction(self.db):
            # Row-lock the booking now, then re-check its status under the lock.
            # This closes the race where a cancel and a pay request land at nearly
            # the same instant - whichever transaction commits first wins, and the
            # second one sees the *post-commit* state, not a stale read.
            locked_booking = self.bookings.get_for_update(booking_id)
            if not locked_booking or locked_booking.status != BookingStatus.PENDING:
                raise BookingNotPayableError()

            existing = self.payments.list_by_booking(booking_id)
            if any(p.status in (PaymentStatus.PENDING, PaymentStatus.SUCCESS) for p in existing):
                raise DuplicateActivePaymentError()

            payment = Payment(booking_id=locked_booking.id, amount=locked_booking.amount, status=PaymentStatus.PENDING)
            payment = self.payments.create(payment)
            self.db.add(PaymentEvent(payment_id=payment.id, status="PENDING", note="Payment initiated"))

        self.db.refresh(payment)

        # Dispatch happens after the transaction commits - never queue a task whose
        # DB row might get rolled back if something above raised.
        from app.tasks.payment_tasks import process_payment_async
        process_payment_async.delay(str(payment.id))

        return payment

    def simulate_processing(self, payment_id: str) -> None:
        payment = self.payments.get_by_id(payment_id)
        if not payment:
            return

        outcome = random.choices(
            [WebhookPaymentStatus.SUCCESS, WebhookPaymentStatus.FAILED],
            weights=[0.85, 0.15],
        )[0]

        payload = WebhookEventPayload(
            event_id=str(uuid.uuid4()),
            booking_id=str(payment.booking_id),
            payment_id=str(payment.id),
            status=outcome,
            provider_ref=f"SIM-{uuid.uuid4().hex[:10].upper()}",
        )

        from app.services.webhook_service import WebhookService
        WebhookService(self.db).handle_event(payload)

    def get_payment(self, payment_id: str, user_id: str) -> Payment:
        payment = self.payments.get_by_id(payment_id)
        if not payment:
            raise BookingNotFoundForPaymentError()
        booking = self.bookings.get_by_id(str(payment.booking_id))
        if not booking or str(booking.user_id) != str(user_id):
            raise ForbiddenPaymentAccessError()
        return payment