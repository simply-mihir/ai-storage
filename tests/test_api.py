"""Tests for the FastAPI application."""

from fastapi.testclient import TestClient

from storage_advisor.app.api import app

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


class TestScenarioEndpoint:
    def test_valid_scenario_returns_200(self):
        resp = client.post("/api/v1/scenarios", json=DEMO_SCENARIO)
        assert resp.status_code == 200
        data = resp.json()
        assert "scenario_id" in data
        assert len(data["scenario_id"]) > 0
        assert data["validation_errors"] == []

    def test_invalid_scenario_returns_400(self):
        bad = {**DEMO_SCENARIO, "expected_users": -1}
        resp = client.post("/api/v1/scenarios", json=bad)
        assert resp.status_code == 400
        data = resp.json()
        assert len(data["validation_errors"]) > 0
        fields = [e["field"] for e in data["validation_errors"]]
        assert any("expected_users" in f for f in fields)


class TestRecommendationEndpoint:
    def test_returns_recommendations(self):
        resp = client.post(
            "/api/v1/recommendations",
            json={"scenario_id": "test-001", "scenario": DEMO_SCENARIO},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_id"] == "test-001"
        assert len(data["recommendations"]) >= 5
        assert "strategy" in data
        assert "impact" in data
        assert "architecture" in data
        assert "generated_at" in data


class TestWhatIfEndpoint:
    def test_growth_change_shows_priority_change(self):
        baseline = {**DEMO_SCENARIO, "daily_growth_gb": 300}
        modified = {**DEMO_SCENARIO, "daily_growth_gb": 1000}
        resp = client.post(
            "/api/v1/what-if",
            json={"baseline_scenario": baseline, "modified_scenario": modified},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["changed_priorities"]) > 0 or len(data["added_techniques"]) > 0
        assert "summary" in data


V2_SCENARIO = {
    **DEMO_SCENARIO,
    "schema_version": 2,
    "rto_hours": 1.0,
    "rpo_hours": 0.25,
    "backup_frequency_per_week": 14,
    "realtime_required": True,
    "ml_required": True,
    "streaming_required": True,
}


class TestV2PayloadAcceptance:
    def test_v2_scenario_accepted(self):
        resp = client.post("/api/v1/scenarios", json=V2_SCENARIO)
        assert resp.status_code == 200
        data = resp.json()
        assert data["normalized"]["schema_version"] == 2
        assert data["normalized"]["rto_hours"] == 1.0

    def test_v1_payload_upconverted(self):
        resp = client.post("/api/v1/scenarios", json=DEMO_SCENARIO)
        assert resp.status_code == 200
        data = resp.json()
        assert data["normalized"]["schema_version"] == 2

    def test_v2_recommendations_surface_new_problems(self):
        resp = client.post(
            "/api/v1/recommendations",
            json={"scenario": V2_SCENARIO},
        )
        assert resp.status_code == 200
        data = resp.json()
        problem_ids = {p["problem_id"] for p in data["problems"]}
        assert "SECURITY_EXPOSURE" in problem_ids
        assert "QUERY_PERFORMANCE_DEGRADATION" in problem_ids

    def test_v1_recommendations_still_work(self):
        resp = client.post(
            "/api/v1/recommendations",
            json={"scenario": DEMO_SCENARIO},
        )
        assert resp.status_code == 200
        assert len(resp.json()["recommendations"]) >= 5


class TestHealthEndpoint:
    def test_returns_all_keys(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        for key in [
            "status", "engine_version", "kb_version",
            "kb_technique_count", "bedrock_available", "uptime_seconds",
        ]:
            assert key in data, f"Missing key: {key}"
        assert data["status"] == "healthy"
        assert data["kb_technique_count"] == 19
