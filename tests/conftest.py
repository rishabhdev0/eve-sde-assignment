import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings
from app.core.redis_client import reset_signup_rate_limit, redis_client
from app.models.user import User
from app.models.centre import DiagnosticCentre
from app.models.test import Test as TestModel
from app.models.centre_test import CentreTest
from app.models.slot import Slot

TEST_DATABASE_URL = settings.DATABASE_URL.replace("/eve_db", "/eve_test_db")

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    # Clear any rate-limit state left over from previous test runs. Redis has no
    # per-test rollback the way the Postgres session does, so without this,
    # repeated runs accumulate real request counts against the same TestClient
    # IP and eventually trip rate limits unrelated to the test itself.
    for key in redis_client.scan_iter("signup_attempts:*"):
        redis_client.delete(key)
    for key in redis_client.scan_iter("login_attempts:*"):
        redis_client.delete(key)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_auth_headers(client, db_session):
    """Factory: signs up, verifies and logs in a user, returns their auth headers."""

    def _make(email: str = "pytest@test.com") -> dict:
        reset_signup_rate_limit("testclient")

        resp = client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": "Str0ng@Pass1"},
        )
        assert resp.status_code == 201, resp.text

        user = db_session.query(User).filter(User.email == email).first()
        user.is_email_verified = True
        db_session.commit()

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Str0ng@Pass1"},
        )
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _make


@pytest.fixture
def auth_headers(make_auth_headers):
    return make_auth_headers("pytest@test.com")


@pytest.fixture
def make_slot(db_session):
    """Factory: creates centre + test + offering + a future slot, returns the slot id."""

    def _make(capacity: int = 2, hours_ahead: int = 48) -> str:
        centre = DiagnosticCentre(id=uuid.uuid4(), name="Slot Centre", location="Test City")
        test_ = TestModel(id=uuid.uuid4(), name=f"Panel {uuid.uuid4()}", description="desc")
        db_session.add_all([centre, test_])
        db_session.flush()

        offering = CentreTest(
            id=uuid.uuid4(), centre_id=centre.id, test_id=test_.id,
            price=500, turnaround_hours=24,
        )
        db_session.add(offering)
        db_session.flush()

        start = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
        slot = Slot(
            id=uuid.uuid4(), centre_test_id=offering.id, start_time=start,
            end_time=start + timedelta(minutes=30), capacity=capacity, booked_count=0,
        )
        db_session.add(slot)
        db_session.commit()
        return str(slot.id)

    return _make

class _FakeTask:
    """Stands in for the Celery task so tests never push jobs to the real broker,
    where the running worker would pick them up."""
    def __init__(self):
        self.dispatched = []

    def delay(self, payment_id):
        self.dispatched.append(payment_id)


@pytest.fixture(autouse=True)
def fake_task(monkeypatch):
    fake = _FakeTask()
    monkeypatch.setattr("app.tasks.payment_tasks.process_payment_async", fake)
    return fake