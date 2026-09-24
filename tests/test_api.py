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
            "kb_stats", "ml_stats",
        ]:
            assert key in data, f"Missing key: {key}"
        assert data["status"] == "healthy"
        assert data["kb_technique_count"] == 19

    def test_kb_stats_matches_loader(self):
        from storage_advisor.domain.problems import ProblemId
        from storage_advisor.kb.loader import discover_families, flatten

        resp = client.get("/health")
        kb = resp.json()["kb_stats"]
        families = discover_families()
        effective = flatten(families)
        assert kb["families"] == len(families)
        assert kb["effective_techniques"] == len(effective)
        assert kb["problems"] == len(ProblemId)
        assert len(kb["categories"]) == 7
        assert kb["exposure"]["legacy"] + kb["exposure"]["v2_only"] == len(effective)

    def test_ml_stats_contract(self):
        resp = client.get("/health")
        ml = resp.json()["ml_stats"]
        assert ml["metric"] == "second_opinion_holdout_jaccard"
        assert ml["threshold"] == 0.80


class TestInsightsEndpoint:
    def test_get_insights_returns_figures(self):
        resp = client.get("/api/v1/insights?dark=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "figures" in data
        assert "catalog" in data
        for key in ("treemap", "industry_heatmap", "correlation", "bubble", "graph"):
            assert key in data["figures"]


class TestSecondOpinionEndpoint:
    def test_second_opinion_contract_wrapped_scenario(self):
        resp = client.post("/api/v1/second-opinion", json={"scenario": DEMO_SCENARIO})
        assert resp.status_code == 200
        data = resp.json()
        assert "agreement_pct" in data
        assert isinstance(data["agreement_pct"], (int, float))
        assert 0.0 <= data["agreement_pct"] <= 100.0

        assert "ml_adds" in data
        assert isinstance(data["ml_adds"], list)
        assert "ml_drops" in data
        assert isinstance(data["ml_drops"], list)

        assert "reasons" in data
        assert isinstance(data["reasons"], dict)
        assert "divergences" in data
        assert isinstance(data["divergences"], list)

        for div in data["divergences"]:
            assert "technique_id" in div
            assert div["type"] in ("add", "drop")
            assert "reason" in div
            assert "Driven by" in div["reason"]
            assert div["technique_id"] in data["reasons"]

    def test_second_opinion_contract_direct_scenario(self):
        resp = client.post("/api/v1/second-opinion", json=DEMO_SCENARIO)
        assert resp.status_code == 200
        data = resp.json()
        assert "agreement_pct" in data
        assert isinstance(data["ml_adds"], list)
        assert isinstance(data["ml_drops"], list)

    def test_determinism_at_fixed_seed(self):
        resp1 = client.post("/api/v1/second-opinion", json={"scenario": V2_SCENARIO})
        resp2 = client.post("/api/v1/second-opinion", json={"scenario": V2_SCENARIO})
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        data1 = resp1.json()
        data2 = resp2.json()
        assert data1["agreement_pct"] == data2["agreement_pct"]
        assert data1["ml_adds"] == data2["ml_adds"]
        assert data1["ml_drops"] == data2["ml_drops"]
        assert data1["reasons"] == data2["reasons"]

    def test_invalid_scenario_returns_400(self):
        bad = {**DEMO_SCENARIO, "expected_users": -99}
        resp = client.post("/api/v1/second-opinion", json={"scenario": bad})
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_engine_authority_untouched(self):
        from storage_advisor.domain.scenario import Scenario
        from storage_advisor.knowledge.technique_catalog import load_techniques
        from storage_advisor.recommendation.recommendation_engine import (
            run_recommendation_engine,
        )

        scenario = Scenario(**DEMO_SCENARIO)
        pure_engine_result = run_recommendation_engine(scenario, load_techniques())
        pure_ids = [r.technique_id for r in pure_engine_result.recommendations]

        resp = client.post("/api/v1/second-opinion", json={"scenario": DEMO_SCENARIO})
        data = resp.json()
        assert data["engine_authority"] is True
        assert data["role"] == "advisory"
        assert data["engine_recommendations"] == pure_ids

