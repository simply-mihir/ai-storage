"""Tests for authentication and rate limiting security middleware."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from storage_advisor.app.api import app
from storage_advisor.app.security import (
    DEV_DEMO_KEY,
    get_rate_limiter,
)


@pytest.fixture(autouse=True)
def reset_limiter_state():
    """Reset rate limiter buckets before and after each test."""
    limiter = get_rate_limiter()
    limiter.reset()
    yield
    limiter.reset()


def test_health_exempt_from_auth():
    """Health check endpoint is exempt from authentication."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_config_endpoint_returns_config_without_auth():
    """Config endpoint is accessible without an API key."""
    client = TestClient(app)
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "env" in data
    assert "apiKey" in data
    assert "rateLimit" in data


def test_missing_api_key_in_production_returns_401(monkeypatch):
    """Missing API key in production environment returns 401."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("API_KEYS", "prod-secret-key-1,prod-secret-key-2")

    client = TestClient(app)
    resp = client.get("/api/v1/pricing")
    assert resp.status_code == 401
    assert "error" in resp.json()
    assert "Unauthorized" in resp.json()["error"]


def test_invalid_api_key_returns_401(monkeypatch):
    """Invalid API key returns 401 in all environments."""
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("API_KEYS", "valid-key-123")

    client = TestClient(app)
    resp = client.get("/api/v1/pricing", headers={"X-API-Key": "invalid-bogus-key"})
    assert resp.status_code == 401
    assert "Unauthorized" in resp.json()["error"]


def test_dev_demo_key_rejected_in_production(monkeypatch):
    """The dev demo key is strictly gated to dev and rejected in production."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("API_KEYS", "prod-secret-key-1")

    client = TestClient(app)
    resp = client.get("/api/v1/pricing", headers={"X-API-Key": DEV_DEMO_KEY})
    assert resp.status_code == 401


def test_valid_configured_api_key_returns_200(monkeypatch):
    """Valid key from API_KEYS environment variable returns 200."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("API_KEYS", "prod-key-alpha,prod-key-beta")

    client = TestClient(app)
    resp = client.get("/api/v1/pricing", headers={"X-API-Key": "prod-key-alpha"})
    assert resp.status_code == 200
    assert "s3_per_gb" in resp.json()


def test_dev_demo_key_returns_200_in_dev_mode(monkeypatch):
    """Dev demo key succeeds when ENV=dev."""
    monkeypatch.setenv("ENV", "dev")
    client = TestClient(app)
    resp = client.get("/api/v1/pricing", headers={"X-API-Key": DEV_DEMO_KEY})
    assert resp.status_code == 200


def test_dev_mode_fallback_when_header_omitted(monkeypatch):
    """In development mode, omitting the key header falls back to dev demo key."""
    monkeypatch.setenv("ENV", "dev")
    client = TestClient(app)
    resp = client.get("/api/v1/pricing")
    assert resp.status_code == 200


def test_rate_limiting_60_req_per_min_returns_429(monkeypatch):
    """Exceeding 60 requests per minute returns 429 with Retry-After header."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("API_KEYS", "rate-limit-test-key")

    client = TestClient(app)
    headers = {"X-API-Key": "rate-limit-test-key"}

    # Exhaust the 60 tokens
    for i in range(60):
        resp = client.get("/api/v1/pricing", headers=headers)
        assert resp.status_code == 200, f"Request {i+1} failed"

    # 61st request should be rate-limited
    resp_429 = client.get("/api/v1/pricing", headers=headers)
    assert resp_429.status_code == 429
    assert "Retry-After" in resp_429.headers
    retry_after = int(resp_429.headers["Retry-After"])
    assert retry_after >= 1
    assert "Too Many Requests" in resp_429.json()["error"]

    # Different key is NOT rate limited
    monkeypatch.setenv("API_KEYS", "rate-limit-test-key,second-key")
    resp_other = client.get("/api/v1/pricing", headers={"X-API-Key": "second-key"})
    assert resp_other.status_code == 200
