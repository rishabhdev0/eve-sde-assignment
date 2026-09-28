from datetime import datetime, timedelta, timezone
import uuid


def _create_centre(client, headers, name="Test Centre", location="Test City"):
    resp = client.post("/api/v1/centres/", json={"name": name, "location": location}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def _create_test(client, headers, name="CBC"):
    resp = client.post("/api/v1/tests/", json={"name": name, "description": "desc"}, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def _offer(client, headers, centre_id, test_id, price=500):
    return client.post(
        f"/api/v1/centres/{centre_id}/tests",
        json={"test_id": test_id, "price": price, "turnaround_hours": 24},
        headers=headers,
    )


def _future(hours=48):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _slot_payload(offering_id, start_hours=48, capacity=2):
    return {
        "centre_test_id": offering_id,
        "start_time": _future(start_hours),
        "end_time": _future(start_hours + 1),
        "capacity": capacity,
    }


def test_creating_a_centre_requires_authentication(client):
    resp = client.post("/api/v1/centres/", json={"name": "X", "location": "Y"})
    assert resp.status_code == 403


def test_create_and_list_centres(client, auth_headers):
    created = _create_centre(client, auth_headers, name="Apollo", location="Mumbai")

    resp = client.get("/api/v1/centres/")
    assert resp.status_code == 200
    assert created["id"] in [c["id"] for c in resp.json()]


def test_unknown_centre_returns_404(client):
    resp = client.get(f"/api/v1/centres/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_attach_test_to_centre_and_list_offerings(client, auth_headers):
    centre = _create_centre(client, auth_headers)
    test_ = _create_test(client, auth_headers)

    resp = _offer(client, auth_headers, centre["id"], test_["id"], price=500)
    assert resp.status_code == 201
    assert resp.json()["test_name"] == "CBC"
    assert float(resp.json()["price"]) == 500

    listing = client.get(f"/api/v1/centres/{centre['id']}/tests")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_attaching_an_unknown_test_returns_404(client, auth_headers):
    centre = _create_centre(client, auth_headers)
    resp = _offer(client, auth_headers, centre["id"], str(uuid.uuid4()))
    assert resp.status_code == 404


def test_attaching_the_same_test_twice_is_rejected(client, auth_headers):
    centre = _create_centre(client, auth_headers)
    test_ = _create_test(client, auth_headers)

    assert _offer(client, auth_headers, centre["id"], test_["id"]).status_code == 201
    assert _offer(client, auth_headers, centre["id"], test_["id"]).status_code == 400


def test_create_slot_and_list_available_slots(client, auth_headers):
    centre = _create_centre(client, auth_headers)
    test_ = _create_test(client, auth_headers)
    offering = _offer(client, auth_headers, centre["id"], test_["id"]).json()

    resp = client.post("/api/v1/slots/", json=_slot_payload(offering["id"]), headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["booked_count"] == 0
    assert resp.json()["is_available"] is True

    listing = client.get("/api/v1/slots/", params={"centre_test_id": offering["id"]})
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_duplicate_slot_at_same_time_is_rejected(client, auth_headers):
    centre = _create_centre(client, auth_headers)
    test_ = _create_test(client, auth_headers)
    offering = _offer(client, auth_headers, centre["id"], test_["id"]).json()

    payload = _slot_payload(offering["id"])
    assert client.post("/api/v1/slots/", json=payload, headers=auth_headers).status_code == 201
    assert client.post("/api/v1/slots/", json=payload, headers=auth_headers).status_code == 400


def test_slot_in_the_past_is_rejected(client, auth_headers):
    centre = _create_centre(client, auth_headers)
    test_ = _create_test(client, auth_headers)
    offering = _offer(client, auth_headers, centre["id"], test_["id"]).json()

    payload = _slot_payload(offering["id"], start_hours=-5)
    resp = client.post("/api/v1/slots/", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_centre_list_respects_pagination_limit(client, auth_headers):
    for i in range(3):
        _create_centre(client, auth_headers, name=f"Centre {i}")

    resp = client.get("/api/v1/centres/", params={"limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 2