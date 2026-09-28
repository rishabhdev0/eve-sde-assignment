import uuid


def _book(client, headers, slot_id):
    resp = client.post("/api/v1/bookings/", json={"slot_id": slot_id}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _pay(client, headers, booking_id):
    return client.post("/api/v1/payments/", json={"booking_id": booking_id}, headers=headers)


def test_payment_requires_authentication(client):
    resp = client.post("/api/v1/payments/", json={"booking_id": str(uuid.uuid4())})
    assert resp.status_code == 403


def test_payment_for_unknown_booking_returns_404(client, auth_headers):
    assert _pay(client, auth_headers, str(uuid.uuid4())).status_code == 404


def test_creating_a_payment_returns_pending_and_dispatches_one_task(client, auth_headers, make_slot, fake_task):
    booking = _book(client, auth_headers, make_slot())

    resp = _pay(client, auth_headers, booking["id"])

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["booking_id"] == booking["id"]
    assert float(body["amount"]) == 500
    assert fake_task.dispatched == [body["id"]]


def test_second_payment_on_same_booking_is_rejected(client, auth_headers, make_slot, fake_task):
    booking = _book(client, auth_headers, make_slot())

    assert _pay(client, auth_headers, booking["id"]).status_code == 202
    assert _pay(client, auth_headers, booking["id"]).status_code == 400
    assert len(fake_task.dispatched) == 1  # the rejected attempt queued nothing


def test_cannot_pay_for_someone_elses_booking(client, make_auth_headers, make_slot):
    owner = make_auth_headers("owner@test.com")
    other = make_auth_headers("other@test.com")
    booking = _book(client, owner, make_slot())

    assert _pay(client, other, booking["id"]).status_code == 403


def test_cannot_pay_for_a_cancelled_booking(client, auth_headers, make_slot):
    booking = _book(client, auth_headers, make_slot())
    cancel = client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=auth_headers)
    assert cancel.status_code == 200

    assert _pay(client, auth_headers, booking["id"]).status_code == 400


def test_only_the_owner_can_read_a_payment(client, make_auth_headers, make_slot):
    owner = make_auth_headers("owner@test.com")
    other = make_auth_headers("other@test.com")
    booking = _book(client, owner, make_slot())
    payment = _pay(client, owner, booking["id"]).json()

    assert client.get(f"/api/v1/payments/{payment['id']}", headers=owner).status_code == 200
    assert client.get(f"/api/v1/payments/{payment['id']}", headers=other).status_code == 403


def test_reading_an_unknown_payment_returns_404(client, auth_headers):
    resp = client.get(f"/api/v1/payments/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404