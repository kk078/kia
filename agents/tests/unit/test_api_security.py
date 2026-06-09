"""Tests for API key auth + rate limiting middleware."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api import security
from api.main import app
from brain_core.config import settings


@pytest.fixture
def client() -> TestClient:
    """Test client against the real app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_security(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Default every test to auth-off, limiter-off, fresh limiter state."""
    monkeypatch.setattr(settings, "kia_api_key", "")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)
    security._limiter = None
    yield
    security._limiter = None


class TestApiKeyAuth:
    """KIA_API_KEY enforcement."""

    def test_no_key_configured_allows_requests(self, client: TestClient) -> None:
        assert client.get("/api/v1/status").status_code == 200

    def test_missing_key_rejected(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "kia_api_key", "sekret")
        response = client.get("/api/v1/status")
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_wrong_key_rejected(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "kia_api_key", "sekret")
        response = client.get("/api/v1/status", headers={"X-API-Key": "wrong"})
        assert response.status_code == 401

    def test_bearer_token_accepted(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "kia_api_key", "sekret")
        response = client.get("/api/v1/status", headers={"Authorization": "Bearer sekret"})
        assert response.status_code == 200

    def test_x_api_key_header_accepted(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "kia_api_key", "sekret")
        response = client.get("/api/v1/status", headers={"X-API-Key": "sekret"})
        assert response.status_code == 200

    def test_health_exempt_from_auth(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "kia_api_key", "sekret")
        assert client.get("/health").status_code == 200

    def test_metrics_exempt_from_auth(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "kia_api_key", "sekret")
        assert client.get("/metrics").status_code == 200


class TestRateLimiting:
    """Per-client sliding-window rate limiting."""

    def test_under_limit_allowed(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "rate_limit_per_minute", 5)
        for _ in range(5):
            assert client.get("/api/v1/status").status_code == 200

    def test_over_limit_rejected_with_retry_after(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
        for _ in range(3):
            assert client.get("/api/v1/status").status_code == 200
        response = client.get("/api/v1/status")
        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) >= 1

    def test_health_exempt_from_rate_limit(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "rate_limit_per_minute", 1)
        for _ in range(5):
            assert client.get("/health").status_code == 200

    def test_window_frees_slots(self) -> None:
        limiter = security.SlidingWindowLimiter(limit=2, window=0.05)
        assert limiter.allow("c")[0]
        assert limiter.allow("c")[0]
        allowed, retry = limiter.allow("c")
        assert not allowed and retry > 0
        import time

        time.sleep(0.06)
        assert limiter.allow("c")[0]

    def test_clients_limited_independently(self) -> None:
        limiter = security.SlidingWindowLimiter(limit=1, window=60.0)
        assert limiter.allow("a")[0]
        assert not limiter.allow("a")[0]
        assert limiter.allow("b")[0]
