"""Tests for the Postgres system of record with graceful degradation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from storage_advisor.db import record


class TestGracefulDegradation:
    """Prove the app continues serving when PG is unreachable."""

    def setup_method(self):
        record.reset()

    def test_save_returns_false_when_no_database_url(self):
        with patch.dict("os.environ", {}, clear=True):
            record.reset()
            result = record.save_scenario("test-id", {"key": "value"})
            assert result is False

    def test_get_returns_none_when_no_database_url(self):
        with patch.dict("os.environ", {}, clear=True):
            record.reset()
            result = record.get_scenario("test-id")
            assert result is None

    def test_save_returns_false_when_connection_fails(self):
        with patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgresql://bad:bad@localhost:19999/nope"},
        ):
            record.reset()
            result = record.save_scenario("test-id", {"key": "value"})
            assert result is False

    def test_get_returns_none_when_connection_fails(self):
        with patch.dict(
            "os.environ",
            {"DATABASE_URL": "postgresql://bad:bad@localhost:19999/nope"},
        ):
            record.reset()
            result = record.get_scenario("test-id")
            assert result is None

    def test_api_still_works_without_pg(self):
        """POST /api/v1/scenarios succeeds even when PG is down."""
        with patch.dict("os.environ", {}, clear=True):
            record.reset()
            from fastapi.testclient import TestClient

            from storage_advisor.app.api import app
            client = TestClient(app)
            resp = client.post("/api/v1/scenarios", json={
                "business_domain": "AI",
                "company_size": "MEDIUM",
                "data_types": ["TEXT"],
                "structured_data_pct": 50,
                "semi_structured_data_pct": 30,
                "unstructured_data_pct": 20,
                "compliance_requirements": ["NONE"],
            })
            assert resp.status_code == 200
            assert "scenario_id" in resp.json()


@pytest.mark.skipif(
    not record._get_database_url(),
    reason="DATABASE_URL not set — skip PG round-trip test",
)
class TestPgRoundTrip:
    """Round-trip test requires a live Postgres instance."""

    def test_save_and_retrieve(self):
        record.reset()
        sid = "roundtrip-test-id"
        payload = {"business_domain": "test", "users": 100}
        saved = record.save_scenario(sid, payload, report_md="# Test Report")
        assert saved is True

        retrieved = record.get_scenario(sid)
        assert retrieved is not None
        assert retrieved["id"] == sid
        assert retrieved["payload"]["business_domain"] == "test"
        assert retrieved["report_md"] == "# Test Report"
