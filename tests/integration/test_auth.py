def test_signup_then_login_requires_verification(client):
    resp = client.post("/api/v1/auth/signup", json={"email": "flow@test.com", "password": "Str0ng@Pass1"})
    assert resp.status_code == 201

    resp = client.post("/api/v1/auth/login", json={"email": "flow@test.com", "password": "Str0ng@Pass1"})
    assert resp.status_code == 403  # email not verified yet


def test_weak_password_rejected(client):
    resp = client.post("/api/v1/auth/signup", json={"email": "weak@test.com", "password": "weak"})
    assert resp.status_code == 422


def test_login_wrong_password_and_nonexistent_user_return_identical_error(client):
    client.post("/api/v1/auth/signup", json={"email": "real@test.com", "password": "Str0ng@Pass1"})

    resp1 = client.post("/api/v1/auth/login", json={"email": "real@test.com", "password": "WrongPass1@"})
    resp2 = client.post("/api/v1/auth/login", json={"email": "ghost@test.com", "password": "WrongPass1@"})

    assert resp1.status_code == 401
    assert resp2.status_code == 401
    assert resp1.json()["detail"] == resp2.json()["detail"]  # no enumeration signal