import pytest

from app.tasks import payment_tasks

# process_payment_async is wrapped in Celery's PromiseProxy, and accessing .run on it
# auto-binds the real task instance as `self` (since functions are descriptors).
# `.__func__` strips that binding so we can supply our own fake `self` instead.
_REAL_RUN = payment_tasks.process_payment_async.run.__func__


class _RetryTriggered(Exception):
    """Marker raised by our fake self.retry() so we can assert it was called."""
    pass


class _FakeCeleryTask:
    def retry(self, exc=None):
        raise _RetryTriggered() from exc


def test_process_payment_async_retries_when_simulate_processing_raises(monkeypatch):
    def _boom(self, payment_id):
        raise RuntimeError("simulated gateway crash")

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.simulate_processing", _boom
    )

    with pytest.raises(_RetryTriggered):
        _REAL_RUN(_FakeCeleryTask(), "some-payment-id")


def test_process_payment_async_does_not_retry_on_success(monkeypatch):
    calls = []

    def _ok(self, payment_id):
        calls.append(payment_id)

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.simulate_processing", _ok
    )

    # Should return cleanly, no exception, no retry() call
    _REAL_RUN(_FakeCeleryTask(), "some-payment-id")

    assert calls == ["some-payment-id"]