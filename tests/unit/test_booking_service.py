import uuid
import pytest
from app.models.user import User
from app.models.slot import Slot
from app.models.centre import DiagnosticCentre
from app.models.test import Test
from app.models.centre_test import CentreTest
from app.services.booking_service import BookingService, SlotFullError, DuplicateActiveBookingError


def _make_user(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@test.com", hashed_password="x", is_email_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _make_slot(db_session, capacity=1):
    centre = DiagnosticCentre(id=uuid.uuid4(), name="Test Centre", location="Test City")
    test_ = Test(id=uuid.uuid4(), name=f"Test Panel {uuid.uuid4()}", description="desc")
    db_session.add_all([centre, test_])
    db_session.flush()

    offering = CentreTest(id=uuid.uuid4(), centre_id=centre.id, test_id=test_.id, price=500, turnaround_hours=24)
    db_session.add(offering)
    db_session.flush()

    slot = Slot(id=uuid.uuid4(), centre_test_id=offering.id, start_time="2026-11-01T09:00:00Z",
                end_time="2026-11-01T09:30:00Z", capacity=capacity, booked_count=0)
    db_session.add(slot)
    db_session.commit()
    return slot


def test_booking_a_full_slot_raises_slot_full_error(db_session):
    slot = _make_slot(db_session, capacity=1)
    user_a = _make_user(db_session)
    user_b = _make_user(db_session)

    service = BookingService(db_session)
    service.create_booking(str(user_a.id), str(slot.id))

    with pytest.raises(SlotFullError):
        service.create_booking(str(user_b.id), str(slot.id))


def test_duplicate_active_booking_same_user_same_slot_rejected(db_session):
    slot = _make_slot(db_session, capacity=2)
    user = _make_user(db_session)

    service = BookingService(db_session)
    service.create_booking(str(user.id), str(slot.id))

    with pytest.raises(DuplicateActiveBookingError):
        service.create_booking(str(user.id), str(slot.id))


def test_cancel_booking_releases_slot_capacity(db_session):
    slot = _make_slot(db_session, capacity=1)
    user = _make_user(db_session)

    service = BookingService(db_session)
    booking = service.create_booking(str(user.id), str(slot.id))
    db_session.refresh(slot)
    assert slot.booked_count == 1

    service.cancel_booking(str(booking.id), str(user.id))
    db_session.refresh(slot)
    assert slot.booked_count == 0