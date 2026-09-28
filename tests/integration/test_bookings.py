def test_unauthenticated_booking_request_rejected(client):
    resp = client.post("/api/v1/bookings/", json={"slot_id": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 403  # HTTPBearer's default behavior when no Authorization header present


def test_booking_nonexistent_slot_returns_404(client, auth_headers):
    resp = client.post("/api/v1/bookings/", json={"slot_id": "00000000-0000-0000-0000-000000000000"}, headers=auth_headers)
    assert resp.status_code == 404