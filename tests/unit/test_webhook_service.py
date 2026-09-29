import uuid
from decimal import Decimal
import pytest
from app.models.user import User
from app.models.centre import DiagnosticCentre
from app.models.test import Test
from app.models.centre_test import CentreTest
from app.models.slot import Slot
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.webhook import WebhookEventPayload, WebhookPaymentStatus
from app.services.webhook_service import (
    WebhookService,
    WebhookBookingNotFoundError,
    WebhookPaymentNotFoundError,
)


def _make_user(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com", hashed_password="x", is_email_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _make_slot(db_session):
    centre = DiagnosticCentre(id=uuid.uuid4(), name="Test Centre", location="Test City")
    test_ = Test(id=uuid.uuid4(), name=f"Test Panel {uuid.uuid4()}", description="desc")
    db_session.add_all([centre, test_])
    db_session.flush()

    offering = CentreTest(id=uuid.uuid4(), centre_id=centre.id, test_id=test_.id, price=500, turnaround_hours=24)
    db_session.add(offering)
    db_session.flush()

    slot = Slot(id=uuid.uuid4(), centre_test_id=offering.id, start_time="2026-11-01T09:00:00Z",
                end_time="2026-11-01T09:30:00Z", capacity=1, booked_count=1)
    db_session.add(slot)
    db_session.flush()
    return slot, offering


def _make_booking_and_payment(db_session):
    user = _make_user(db_session)
    slot, offering = _make_slot(db_session)

    booking = Booking(
        id=uuid.uuid4(), user_id=user.id, slot_id=slot.id,
        centre_test_id=offering.id, amount=Decimal("500.00"), status=BookingStatus.PENDING,
    )
    db_session.add(booking)
    db_session.flush()

    payment = Payment(id=uuid.uuid4(), booking_id=booking.id, amount=booking.amount, status=PaymentStatus.PENDING)
    db_session.add(payment)
    db_session.commit()
    return booking, payment

def _unique_event_id() -> str:
    # Redis doesn't reset between test runs, so a fixed event_id would still look "seen" - always make a new one.
    return f"test-event-{uuid.uuid4()}"

def test_webhook_processes_new_event_and_confirms_booking(db_session):
    booking, payment = _make_booking_and_payment(db_session)

    payload = WebhookEventPayload(
        event_id=_unique_event_id(), booking_id=str(booking.id), payment_id=str(payment.id),
        status=WebhookPaymentStatus.SUCCESS, provider_ref="TEST-REF-1",
    )
    result = WebhookService(db_session).handle_event(payload)

    assert result["status"] == "processed"
    db_session.refresh(booking)
    db_session.refresh(payment)
    assert booking.status == BookingStatus.CONFIRMED
    assert payment.status == PaymentStatus.SUCCESS


def test_duplicate_event_id_is_ignored_and_does_not_reprocess(db_session):
    booking, payment = _make_booking_and_payment(db_session)
    event_id = _unique_event_id()

    payload = WebhookEventPayload(
        event_id=event_id, booking_id=str(booking.id), payment_id=str(payment.id),
        status=WebhookPaymentStatus.SUCCESS, provider_ref="TEST-REF-2",
    )

    first_result = WebhookService(db_session).handle_event(payload)
    second_result = WebhookService(db_session).handle_event(payload)  # same event_id, sent again

    assert first_result["status"] == "processed"
    assert second_result["status"] == "duplicate_ignored"

    db_session.refresh(booking)
    db_session.refresh(payment)
    assert booking.status == BookingStatus.CONFIRMED
    assert payment.status == PaymentStatus.SUCCESS


def test_already_resolved_payment_ignores_new_event_with_different_id(db_session):
    booking, payment = _make_booking_and_payment(db_session)

    first_payload = WebhookEventPayload(
        event_id=_unique_event_id(), booking_id=str(booking.id), payment_id=str(payment.id),
        status=WebhookPaymentStatus.SUCCESS, provider_ref="TEST-REF-3",
    )
    WebhookService(db_session).handle_event(first_payload)

    second_payload = WebhookEventPayload(
        event_id=_unique_event_id(),  # genuinely different event_id, same payment
        booking_id=str(booking.id), payment_id=str(payment.id),
        status=WebhookPaymentStatus.FAILED, provider_ref="TEST-REF-4",
    )
    result = WebhookService(db_session).handle_event(second_payload)

    assert result["status"] == "already_resolved"
    db_session.refresh(booking)
    db_session.refresh(payment)
    assert booking.status == BookingStatus.CONFIRMED  # not flipped to FAILED
    assert payment.status == PaymentStatus.SUCCESS


def test_webhook_for_missing_booking_raises_404(db_session):
    payload = WebhookEventPayload(
        event_id=_unique_event_id(), booking_id=str(uuid.uuid4()), payment_id=str(uuid.uuid4()),
        status=WebhookPaymentStatus.SUCCESS, provider_ref="TEST-REF-5",
    )
    with pytest.raises(WebhookBookingNotFoundError):
        WebhookService(db_session).handle_event(payload)


def test_webhook_for_missing_payment_raises_404(db_session):
    booking, _ = _make_booking_and_payment(db_session)

    payload = WebhookEventPayload(
        event_id=_unique_event_id(), booking_id=str(booking.id), payment_id=str(uuid.uuid4()),
        status=WebhookPaymentStatus.SUCCESS, provider_ref="TEST-REF-8",
    )
    with pytest.raises(WebhookPaymentNotFoundError):
        WebhookService(db_session).handle_event(payload)


def test_success_webhook_after_booking_cancelled_triggers_auto_refund(db_session):
    """The stuck-payment scenario: user cancels while payment is still in flight."""
    booking, payment = _make_booking_and_payment(db_session)
    booking.status = BookingStatus.CANCELLED
    db_session.commit()

    payload = WebhookEventPayload(
        event_id=_unique_event_id(), booking_id=str(booking.id), payment_id=str(payment.id),
        status=WebhookPaymentStatus.SUCCESS, provider_ref="TEST-REF-6",
    )
    result = WebhookService(db_session).handle_event(payload)

    assert result["status"] == "processed_with_auto_refund"
    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == PaymentStatus.SUCCESS      # payment is resolved, not stuck PENDING
    assert booking.status == BookingStatus.CANCELLED    # booking stays cancelled

    refunds = db_session.query(Payment).filter(Payment.refunded_payment_id == payment.id).all()
    assert len(refunds) == 1
    assert refunds[0].status == PaymentStatus.REFUNDED


def test_failed_webhook_after_booking_cancelled_resolves_payment_without_error(db_session):
    booking, payment = _make_booking_and_payment(db_session)
    booking.status = BookingStatus.CANCELLED
    db_session.commit()

    payload = WebhookEventPayload(
        event_id=_unique_event_id(), booking_id=str(booking.id), payment_id=str(payment.id),
        status=WebhookPaymentStatus.FAILED, provider_ref="TEST-REF-7",
    )
    result = WebhookService(db_session).handle_event(payload)

    assert result["status"] == "processed_terminal_booking"
    db_session.refresh(payment)
    assert payment.status == PaymentStatus.FAILED