from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.repositories.booking_repository import BookingRepository
from app.repositories.slot_repository import SlotRepository
from app.repositories.centre_repository import CentreRepository
from app.repositories.payment_repository import PaymentRepository
from app.models.booking import Booking, BookingStatus
from app.models.booking_event import BookingEvent
from app.models.payment import Payment, PaymentStatus
from app.models.payment_event import PaymentEvent
from app.db.transaction import transaction
from app.core.exceptions import AppException


class SlotNotFoundError(AppException):
    status_code = 404
    detail = "Slot not found"


class SlotFullError(AppException):
    status_code = 409
    detail = "This slot is fully booked"


class SlotExpiredError(AppException):
    status_code = 400
    detail = "This slot's time has already passed"


class BookingNotFoundError(AppException):
    status_code = 404
    detail = "Booking not found"


class ForbiddenBookingAccessError(AppException):
    status_code = 403
    detail = "You do not have access to this booking"


class InvalidBookingStateError(AppException):
    status_code = 400
    detail = "This booking cannot be modified from its current state"


class DuplicateActiveBookingError(AppException):
    status_code = 400
    detail = "You already have an active booking for this slot"


ALLOWED_TRANSITIONS = {
    BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.CANCELLED},
    BookingStatus.FAILED: set(),
    BookingStatus.CANCELLED: set(),
}

# Booking is done needing its seat once it hits FAILED or CANCELLED - not CONFIRMED,
# that one's still holding a real appointment.
SEAT_RELEASING_STATUSES = {BookingStatus.FAILED, BookingStatus.CANCELLED}


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.bookings = BookingRepository(db)
        self.slots = SlotRepository(db)
        self.centres = CentreRepository(db)

    def _log_event(self, booking_id: str, from_status: str | None, to_status: str, triggered_by: str):
        self.db.add(BookingEvent(
            booking_id=booking_id, from_status=from_status, to_status=to_status, triggered_by=triggered_by,
        ))

    def transition(self, booking: Booking, new_status: BookingStatus, triggered_by: str):
        current = booking.status
        if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
            raise InvalidBookingStateError(
                f"Cannot transition booking from {current.value} to {new_status.value}"
            )
        old = current.value
        booking.status = new_status
        self._log_event(booking.id, old, new_status.value, triggered_by)

        # Free the seat whenever a booking ends up FAILED or CANCELLED, no matter
        # what triggered it - user cancelling, a failed payment, or reconciliation.
        if new_status in SEAT_RELEASING_STATUSES:
            slot = self.slots.get_for_update(str(booking.slot_id))
            if slot and slot.booked_count > 0:
                slot.booked_count -= 1

    def create_booking(self, user_id: str, slot_id: str) -> Booking:
        with transaction(self.db):
            # Locking the slot first is what actually stops the race - two people
            # booking the same slot at once now get serialized here, so the second
            # one always sees the first one's booking before it checks anything.
            slot = self.slots.get_for_update(slot_id)
            if not slot:
                raise SlotNotFoundError()

            if self.bookings.get_active_booking_for_user_slot(user_id, slot_id):
                raise DuplicateActiveBookingError()

            if slot.booked_count >= slot.capacity:
                raise SlotFullError()
            if slot.start_time < datetime.now(timezone.utc):
                raise SlotExpiredError()

            offering = self.centres.get_centre_test(str(slot.centre_test_id))

            slot.booked_count += 1

            booking = Booking(
                user_id=user_id,
                slot_id=slot.id,
                centre_test_id=slot.centre_test_id,
                amount=offering.price,
                status=BookingStatus.PENDING,
            )
            booking = self.bookings.create(booking)
            self._log_event(booking.id, None, BookingStatus.PENDING.value, "user")

        self.db.refresh(booking)
        return booking

    def get_booking(self, booking_id: str, user_id: str) -> Booking:
        booking = self.bookings.get_by_id(booking_id)
        if not booking:
            raise BookingNotFoundError()
        if str(booking.user_id) != str(user_id):
            raise ForbiddenBookingAccessError()
        return booking

    def list_my_bookings(self, user_id: str, skip: int = 0, limit: int = 20) -> list[Booking]:
        return self.bookings.list_by_user(user_id, skip=skip, limit=limit)

    def cancel_booking(self, booking_id: str, user_id: str) -> Booking:
        with transaction(self.db):
            booking = self.bookings.get_for_update(booking_id)
            if not booking:
                raise BookingNotFoundError()
            if str(booking.user_id) != str(user_id):
                raise ForbiddenBookingAccessError()

            was_confirmed = booking.status == BookingStatus.CONFIRMED

            self.transition(booking, BookingStatus.CANCELLED, "user")

            # If it was CONFIRMED, the payment already went through - cancelling
            # shouldn't leave that charge unreversed. We don't touch the original
            # SUCCESS row, we add a new REFUNDED one pointing back to it, so the
            # history stays honest: charged, then refunded.
            if was_confirmed:
                payments = PaymentRepository(self.db)
                successful_payments = [
                    p for p in payments.list_by_booking(booking_id)
                    if p.status == PaymentStatus.SUCCESS
                ]
                for original in successful_payments:
                    refund = Payment(
                        booking_id=booking_id,
                        amount=original.amount,
                        status=PaymentStatus.REFUNDED,
                        provider_ref=f"REFUND-OF-{original.provider_ref}",
                        refunded_payment_id=original.id,
                    )
                    self.db.add(refund)
                    self.db.flush()
                    self.db.add(PaymentEvent(
                        payment_id=refund.id, status="REFUNDED",
                        note=f"Booking cancelled after confirmation - reversing payment {original.id}",
                    ))

        self.db.refresh(booking)
        return booking