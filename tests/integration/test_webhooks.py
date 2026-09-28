import uuid

from app.core.config import settings
from app.models.payment import Payment, PaymentStatus

WEBHOOK_URL = "/api/v1/payments/webhook/"


def _secret_header():
    return {"x-webhook-secret": settings.WEBHOOK_SHARED_SECRET}


def _event(booking_id, payment_id, status="SUCCESS", event_id=None):
    return {
        "event_id": event_id or f"evt-{uuid.uuid4()}",
        "booking_id": booking_id,
        "payment_id": payment_id,
        "status": status,
        "provider_ref": "TEST-REF",
    }


def _booking_with_payment(client, headers, slot_id):
    booking = client.post("/api/v1/bookings/", json={"slot_id": slot_id}, headers=headers)
    assert booking.status_code == 201, booking.text
    booking = booking.json()

    payment = client.post("/api/v1/payments/", json={"booking_id": booking["id"]}, headers=headers)
    assert payment.status_code == 202, payment.text
    return booking, payment.json()


def _booking_status(client, headers, booking_id):
    return client.get(f"/api/v1/bookings/{booking_id}", headers=headers).json()["status"]


def _payment_status(client, headers, payment_id):
    return client.get(f"/api/v1/payments/{payment_id}", headers=headers).json()["status"]


def _slot_booked_count(client, booking):
    slots = client.get("/api/v1/slots/", params={"centre_test_id": booking["centre_test_id"]}).json()
    return next(s for s in slots if s["id"] == booking["slot_id"])["booked_count"]


def test_webhook_without_secret_header_is_rejected(client):
    body = _event(str(uuid.uuid4()), str(uuid.uuid4()))
    assert client.post(WEBHOOK_URL, json=body).status_code == 422


def test_webhook_with_wrong_secret_is_rejected(client):
    body = _event(str(uuid.uuid4()), str(uuid.uuid4()))
    resp = client.post(WEBHOOK_URL, json=body, headers={"x-webhook-secret": "wrong-secret"})
    assert resp.status_code == 401


def test_webhook_with_invalid_status_is_rejected(client):
    body = _event(str(uuid.uuid4()), str(uuid.uuid4()), status="MAYBE")
    assert client.post(WEBHOOK_URL, json=body, headers=_secret_header()).status_code == 422


def test_webhook_for_unknown_booking_returns_404(client):
    body = _event(str(uuid.uuid4()), str(uuid.uuid4()))
    assert client.post(WEBHOOK_URL, json=body, headers=_secret_header()).status_code == 404


def test_success_webhook_confirms_booking_and_payment(client, auth_headers, make_slot):
    booking, payment = _booking_with_payment(client, auth_headers, make_slot())

    # server-to-server call: no user JWT, only the shared secret
    resp = client.post(WEBHOOK_URL, json=_event(booking["id"], payment["id"]), headers=_secret_header())

    assert resp.status_code == 200
    assert resp.json()["status"] == "processed"
    assert _booking_status(client, auth_headers, booking["id"]) == "CONFIRMED"
    assert _payment_status(client, auth_headers, payment["id"]) == "SUCCESS"


def test_replayed_event_id_is_ignored(client, auth_headers, make_slot):
    booking, payment = _booking_with_payment(client, auth_headers, make_slot())
    body = _event(booking["id"], payment["id"])

    first = client.post(WEBHOOK_URL, json=body, headers=_secret_header())
    second = client.post(WEBHOOK_URL, json=body, headers=_secret_header())

    assert first.json()["status"] == "processed"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate_ignored"
    assert _booking_status(client, auth_headers, booking["id"]) == "CONFIRMED"


def test_failed_webhook_fails_booking_and_releases_the_seat(client, auth_headers, make_slot):
    booking, payment = _booking_with_payment(client, auth_headers, make_slot())
    assert _slot_booked_count(client, booking) == 1

    resp = client.post(WEBHOOK_URL, json=_event(booking["id"], payment["id"], "FAILED"), headers=_secret_header())

    assert resp.json()["status"] == "processed"
    assert _booking_status(client, auth_headers, booking["id"]) == "FAILED"
    assert _payment_status(client, auth_headers, payment["id"]) == "FAILED"
    assert _slot_booked_count(client, booking) == 0


def test_later_conflicting_event_cannot_flip_a_settled_payment(client, auth_headers, make_slot):
    booking, payment = _booking_with_payment(client, auth_headers, make_slot())
    client.post(WEBHOOK_URL, json=_event(booking["id"], payment["id"], "SUCCESS"), headers=_secret_header())

    # a different event_id, so this is not a replay - it tries to fail an already-successful payment
    resp = client.post(WEBHOOK_URL, json=_event(booking["id"], payment["id"], "FAILED"), headers=_secret_header())

    assert resp.json()["status"] == "already_resolved"
    assert _payment_status(client, auth_headers, payment["id"]) == "SUCCESS"
    assert _booking_status(client, auth_headers, booking["id"]) == "CONFIRMED"


def test_success_after_booking_was_cancelled_is_auto_refunded(client, auth_headers, make_slot, db_session):
    """User cancels while the payment is still in flight, then the success webhook arrives."""
    booking, payment = _booking_with_payment(client, auth_headers, make_slot())
    cancel = client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=auth_headers)
    assert cancel.status_code == 200

    resp = client.post(WEBHOOK_URL, json=_event(booking["id"], payment["id"], "SUCCESS"), headers=_secret_header())

    assert resp.status_code == 200
    assert resp.json()["status"] == "processed_with_auto_refund"
    assert _payment_status(client, auth_headers, payment["id"]) == "SUCCESS"   # resolved, not stuck PENDING
    assert _booking_status(client, auth_headers, booking["id"]) == "CANCELLED"  # booking stays cancelled

    refunds = db_session.query(Payment).filter(Payment.refunded_payment_id == uuid.UUID(payment["id"])).all()
    assert len(refunds) == 1
    assert refunds[0].status == PaymentStatus.REFUNDED