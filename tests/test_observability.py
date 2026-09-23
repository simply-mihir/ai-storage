"""Tests for observability: Request IDs, structured JSON logging, and Prometheus metrics."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi.testclient import TestClient

from storage_advisor.app.api import app
from storage_advisor.observability.metrics import metrics_collector

client = TestClient(app)

DEMO_SCENARIO = {
    "business_domain": "AI",
    "company_size": "ENTERPRISE",
    "expected_users": 10_000_000,
    "concurrent_users": 100_000,
    "current_storage_gb": 25_000,
    "daily_growth_gb": 300,
    "data_types": ["IMAGES", "DOCUMENTS", "TRANSACTIONS", "LOGS"],
    "structured_data_pct": 20,
    "semi_structured_data_pct": 20,
    "unstructured_data_pct": 60,
    "read_intensity": "HIGH",
    "write_intensity": "HIGH",
    "access_pattern": "MIXED",
    "latency_requirement_ms": 100,
    "availability_requirement": 99.99,
    "rto_minutes": 60,
    "rpo_minutes": 15,
    "retention_years": 7,
    "budget_level": "HIGH",
    "analytics_required": True,
    "real_time_processing_required": True,
    "sensitive_data": True,
    "encryption_required": True,
    "compliance_requirements": ["NONE"],
}


class TestRequestIdMiddleware:
    def test_request_id_generated_when_missing(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        req_id = resp.headers.get("X-Request-ID")
        assert req_id is not None
        # Must be valid UUID format
        parsed = uuid.UUID(req_id)
        assert str(parsed) == req_id

    def test_request_id_preserved_when_provided(self):
        custom_id = "test-custom-trace-" + str(uuid.uuid4())
        resp = client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID") == custom_id


class TestStructuredLogging:
    def test_caplog_contains_request_id_across_stages(self, caplog):
        custom_id = "stage-trace-" + str(uuid.uuid4())
        caplog.set_level(logging.INFO)

        resp = client.post(
            "/api/v1/recommendations",
            json={"scenario_id": "test-obs-001", "scenario": DEMO_SCENARIO},
            headers={"X-Request-ID": custom_id},
        )
        assert resp.status_code == 200
        assert resp.headers.get("X-Request-ID") == custom_id

        # Extract structured JSON logs emitted by stages
        expected_stages = {
            "profiling",
            "problem_detection",
            "recommendation_engine",
            "impact_estimation",
            "architecture_build",
        }
        found_stages: set[str] = set()

        for record in caplog.records:
            msg = record.getMessage()
            if not msg.startswith("{") or not msg.endswith("}"):
                continue
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue

            if "stage" in data and "request_id" in data:
                assert data["request_id"] == custom_id
                assert "timestamp" in data
                assert "duration_ms" in data
                assert isinstance(data["duration_ms"], (int, float))
                assert data["duration_ms"] >= 0
                found_stages.add(data["stage"])

        assert expected_stages.issubset(found_stages), (
            f"Missing stages in structured logs: {expected_stages - found_stages}"
        )


class TestMetricsEndpoint:
    def test_metrics_endpoint_returns_prometheus_format(self):
        # Trigger requests to ensure metrics are recorded
        client.get("/health")
        client.post(
            "/api/v1/recommendations",
            json={"scenario_id": "test-metric-001", "scenario": DEMO_SCENARIO},
        )
        client.post(
            "/api/v1/explain",
            json={"recommendation": {"rationale": "Test reason", "problems_solved": ["Cost"]}},
        )

        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")

        text = resp.text

        # 1. requests_total
        assert "# HELP requests_total" in text
        assert "# TYPE requests_total counter" in text
        assert "requests_total{" in text

        # 2. stage_duration_seconds
        assert "# HELP stage_duration_seconds" in text
        assert "# TYPE stage_duration_seconds summary" in text
        assert "stage_duration_seconds{" in text
        assert 'stage="profiling"' in text
        assert 'stage="architecture_build"' in text
        assert "stage_duration_seconds_count{" in text
        assert "stage_duration_seconds_sum{" in text

        # 3. ai_fallback_tier
        assert "# HELP ai_fallback_tier" in text
        assert "# TYPE ai_fallback_tier counter" in text
        assert 'ai_fallback_tier{tier="structured_fallback"}' in text

    def test_metrics_collector_direct_methods(self):
        metrics_collector.reset()
        metrics_collector.record_request("/test", "GET", 200)
        metrics_collector.record_stage_duration("test_stage", 0.042)
        metrics_collector.record_ai_fallback_tier("groq")

        text = metrics_collector.export_prometheus_text()
        assert 'requests_total{endpoint="/test",method="GET",status="200"} 1' in text
        assert 'stage_duration_seconds{stage="test_stage",quantile="0.5"} 0.042000' in text
        assert 'stage_duration_seconds_count{stage="test_stage"} 1' in text
        assert 'ai_fallback_tier{tier="groq"} 1' in text
