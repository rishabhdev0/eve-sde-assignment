import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.user import User
from app.models.slot import Slot
from app.models.centre import DiagnosticCentre
from app.models.test import Test as TestModel
from app.models.centre_test import CentreTest
from app.models.booking import BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.payment_event import PaymentEvent
from app.schemas.webhook import WebhookPaymentStatus
from app.services.booking_service import BookingService
from app.services.payment_service import (
    PaymentService,
    BookingNotFoundForPaymentError,
    ForbiddenPaymentAccessError,
    BookingNotPayableError,
    DuplicateActivePaymentError,
)


def _make_user(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com", hashed_password="x", is_email_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _make_booking(db_session, user):
    """Creates centre + test + offering + slot, then books it for `user` via BookingService."""
    centre = DiagnosticCentre(id=uuid.uuid4(), name="Test Centre", location="Test City")
    test_ = TestModel(id=uuid.uuid4(), name=f"Test Panel {uuid.uuid4()}", description="desc")
    db_session.add_all([centre, test_])
    db_session.flush()

    offering = CentreTest(id=uuid.uuid4(), centre_id=centre.id, test_id=test_.id, price=500, turnaround_hours=24)
    db_session.add(offering)
    db_session.flush()

    start = datetime.now(timezone.utc) + timedelta(hours=48)
    slot = Slot(
        id=uuid.uuid4(), centre_test_id=offering.id, start_time=start,
        end_time=start + timedelta(minutes=30), capacity=2, booked_count=0,
    )
    db_session.add(slot)
    db_session.commit()

    return BookingService(db_session).create_booking(str(user.id), str(slot.id))


def _force_outcome(monkeypatch, outcome):
    """Makes simulate_processing's random 85/15 choice deterministic."""
    monkeypatch.setattr("app.services.payment_service.random.choices", lambda *a, **k: [outcome])


# ---------- create_payment ----------

def test_create_payment_for_unknown_booking_raises_not_found(db_session, fake_task):
    user = _make_user(db_session)

    with pytest.raises(BookingNotFoundForPaymentError):
        PaymentService(db_session).create_payment(str(user.id), str(uuid.uuid4()))

    assert fake_task.dispatched == []


def test_create_payment_for_someone_elses_booking_raises_forbidden(db_session, fake_task):
    owner = _make_user(db_session)
    other = _make_user(db_session)
    booking = _make_booking(db_session, owner)

    with pytest.raises(ForbiddenPaymentAccessError):
        PaymentService(db_session).create_payment(str(other.id), str(booking.id))

    assert fake_task.dispatched == []


def test_create_payment_for_non_pending_booking_raises_not_payable(db_session, fake_task):
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)
    booking.status = BookingStatus.CONFIRMED
    db_session.commit()

    with pytest.raises(BookingNotPayableError):
        PaymentService(db_session).create_payment(str(user.id), str(booking.id))

    assert fake_task.dispatched == []


def test_create_payment_for_cancelled_booking_raises_not_payable(db_session, fake_task):
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)
    BookingService(db_session).cancel_booking(str(booking.id), str(user.id))

    with pytest.raises(BookingNotPayableError):
        PaymentService(db_session).create_payment(str(user.id), str(booking.id))

    assert fake_task.dispatched == []


def test_create_payment_happy_path_creates_pending_payment_and_event(db_session, fake_task):
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)

    payment = PaymentService(db_session).create_payment(str(user.id), str(booking.id))

    assert payment.booking_id == booking.id
    assert payment.status == PaymentStatus.PENDING
    assert float(payment.amount) == 500

    events = db_session.query(PaymentEvent).filter(PaymentEvent.payment_id == payment.id).all()
    assert len(events) == 1
    assert events[0].status == "PENDING"
    assert events[0].note == "Payment initiated"


def test_create_payment_dispatches_exactly_one_task_with_payment_id(db_session, fake_task):
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)

    payment = PaymentService(db_session).create_payment(str(user.id), str(booking.id))

    assert fake_task.dispatched == [str(payment.id)]


def test_second_payment_while_first_is_pending_raises_duplicate(db_session, fake_task):
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)
    service = PaymentService(db_session)
    service.create_payment(str(user.id), str(booking.id))

    with pytest.raises(DuplicateActivePaymentError):
        service.create_payment(str(user.id), str(booking.id))

    assert len(fake_task.dispatched) == 1  # the rejected attempt queued nothing


def test_second_payment_after_first_succeeded_raises_duplicate(db_session, fake_task):
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)
    service = PaymentService(db_session)
    first = service.create_payment(str(user.id), str(booking.id))
    first.status = PaymentStatus.SUCCESS
    db_session.commit()

    with pytest.raises(DuplicateActivePaymentError):
        service.create_payment(str(user.id), str(booking.id))

    assert len(fake_task.dispatched) == 1


def test_payment_can_be_retried_after_previous_one_failed(db_session, fake_task):
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)
    service = PaymentService(db_session)
    first = service.create_payment(str(user.id), str(booking.id))
    first.status = PaymentStatus.FAILED
    db_session.commit()

    second = service.create_payment(str(user.id), str(booking.id))

    assert second.id != first.id
    assert second.status == PaymentStatus.PENDING
    assert fake_task.dispatched == [str(first.id), str(second.id)]


# ---------- get_payment ----------

def test_get_payment_unknown_id_raises_not_found(db_session):
    user = _make_user(db_session)

    with pytest.raises(BookingNotFoundForPaymentError):
        PaymentService(db_session).get_payment(str(uuid.uuid4()), str(user.id))


def test_get_payment_by_non_owner_raises_forbidden(db_session, fake_task):
    owner = _make_user(db_session)
    other = _make_user(db_session)
    booking = _make_booking(db_session, owner)
    service = PaymentService(db_session)
    payment = service.create_payment(str(owner.id), str(booking.id))

    with pytest.raises(ForbiddenPaymentAccessError):
        service.get_payment(str(payment.id), str(other.id))


def test_get_payment_by_owner_returns_payment(db_session, fake_task):
    owner = _make_user(db_session)
    booking = _make_booking(db_session, owner)
    service = PaymentService(db_session)
    payment = service.create_payment(str(owner.id), str(booking.id))

    result = service.get_payment(str(payment.id), str(owner.id))

    assert result.id == payment.id


# ---------- simulate_processing ----------

def test_simulate_processing_unknown_payment_returns_quietly(db_session):
    assert PaymentService(db_session).simulate_processing(str(uuid.uuid4())) is None


def test_simulate_processing_success_confirms_booking(db_session, fake_task, monkeypatch):
    _force_outcome(monkeypatch, WebhookPaymentStatus.SUCCESS)
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)
    service = PaymentService(db_session)
    payment = service.create_payment(str(user.id), str(booking.id))

    service.simulate_processing(str(payment.id))

    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == PaymentStatus.SUCCESS
    assert payment.provider_ref.startswith("SIM-")
    assert booking.status == BookingStatus.CONFIRMED

    events = db_session.query(PaymentEvent).filter(PaymentEvent.payment_id == payment.id).all()
    assert sorted(e.status for e in events) == ["PENDING", "SUCCESS"]


def test_simulate_processing_failure_fails_booking(db_session, fake_task, monkeypatch):
    _force_outcome(monkeypatch, WebhookPaymentStatus.FAILED)
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)
    service = PaymentService(db_session)
    payment = service.create_payment(str(user.id), str(booking.id))

    service.simulate_processing(str(payment.id))

    db_session.refresh(payment)
    db_session.refresh(booking)
    assert payment.status == PaymentStatus.FAILED
    assert booking.status == BookingStatus.FAILED


def test_simulate_processing_success_on_cancelled_booking_auto_refunds(db_session, fake_task, monkeypatch):
    _force_outcome(monkeypatch, WebhookPaymentStatus.SUCCESS)
    user = _make_user(db_session)
    booking = _make_booking(db_session, user)
    service = PaymentService(db_session)
    payment = service.create_payment(str(user.id), str(booking.id))

    # Booking gets cancelled while the payment is still in flight.
    booking.status = BookingStatus.CANCELLED
    db_session.commit()

    service.simulate_processing(str(payment.id))

    db_session.refresh(payment)
    assert payment.status == PaymentStatus.SUCCESS

    refund = db_session.query(Payment).filter(Payment.refunded_payment_id == payment.id).one()
    assert refund.status == PaymentStatus.REFUNDED
    assert refund.amount == payment.amount
    assert refund.provider_ref == f"AUTO-REFUND-OF-{payment.provider_ref}"