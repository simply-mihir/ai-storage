"""Tests for BedrockExplainer — fallback paths only (no Bedrock calls)."""

from storage_advisor.domain.recommendations import (
    Priority,
    Recommendation,
    RecommendationResult,
    Strategy,
)
from storage_advisor.domain.scenario import Scenario
from storage_advisor.integrations.bedrock import (
    BedrockExplainer,
    ExplanationResult,
    structured_fallback,
)

_SCENARIO = Scenario(
    business_domain="FINTECH",
    company_size="ENTERPRISE",
    expected_users=5_000_000,
    concurrent_users=50_000,
    current_storage_gb=10_000,
    daily_growth_gb=200,
    data_types=["TRANSACTIONS", "LOGS"],
    structured_data_pct=60,
    semi_structured_data_pct=30,
    unstructured_data_pct=10,
    read_intensity="HIGH",
    write_intensity="HIGH",
    access_pattern="MIXED",
    latency_requirement_ms=50,
    availability_requirement=99.99,
    rto_minutes=30,
    rpo_minutes=5,
    retention_years=7,
    budget_level="HIGH",
    analytics_required=True,
    real_time_processing_required=True,
    sensitive_data=True,
    encryption_required=True,
    compliance_requirements=["PCI", "SOC2"],
)


def _make_recommendation(tid: str, priority: str = "REQUIRED") -> Recommendation:
    return Recommendation(
        technique_id=tid,
        technique_name=tid.replace("_", " ").title(),
        category="general",
        priority=Priority(priority),
        alignment_score=0.85,
        problems_solved=["high_write_volume"],
        rationale=f"Addresses write-heavy workload via {tid}.",
        evidence=["write_intensity=HIGH"],
        benefits=["Improved throughput"],
        disadvantages=["Added complexity"],
        implementation_complexity="MEDIUM",
        prerequisites=[],
        conflicts_with=[],
        conditions=[],
    )


def _make_result() -> RecommendationResult:
    recs = [
        _make_recommendation("write_ahead_log"),
        _make_recommendation("replication", "RECOMMENDED"),
        _make_recommendation("compression", "OPTIONAL"),
    ]
    return RecommendationResult(
        scenario_summary={"domain": "FINTECH", "users": 5_000_000},
        detected_problems=[
            {"problem_id": "high_write_volume", "severity": "HIGH", "evidence": "write_intensity=HIGH"},
            {"problem_id": "high_growth", "severity": "MEDIUM", "evidence": "daily_growth_gb=200"},
        ],
        recommendations=recs,
        strategy=Strategy(general=recs),
        assumptions=["Growth rate remains constant"],
    )


class TestStructuredFallback:
    def test_returns_explanation_result(self):
        result = structured_fallback(_make_result(), _SCENARIO)
        assert isinstance(result, ExplanationResult)
        assert result.source == "structured_fallback"

    def test_mentions_domain_and_users(self):
        result = structured_fallback(_make_result(), _SCENARIO)
        assert "FINTECH" in result.text
        assert "5,000,000" in result.text

    def test_mentions_primary_recommendation(self):
        result = structured_fallback(_make_result(), _SCENARIO)
        assert "write_ahead_log" in result.text

    def test_mentions_problem_count(self):
        result = structured_fallback(_make_result(), _SCENARIO)
        assert "2 architectural pressures" in result.text

    def test_mentions_lead_problem(self):
        result = structured_fallback(_make_result(), _SCENARIO)
        assert "high_write_volume" in result.text

    def test_bedrock_unavailable_note(self):
        result = structured_fallback(_make_result(), _SCENARIO)
        assert "Bedrock explanation unavailable" in result.text


class TestBedrockExplainerFallback:
    def test_init_without_boto3_credentials(self):
        explainer = BedrockExplainer(region="us-west-2")
        assert isinstance(explainer, BedrockExplainer)

    def test_explain_falls_back_when_unavailable(self):
        explainer = BedrockExplainer()
        explainer.available = False
        result = explainer.explain(_make_result(), _SCENARIO)
        assert result.source == "structured_fallback"
        assert "FINTECH" in result.text

    def test_extract_returns_empty_when_unavailable(self):
        explainer = BedrockExplainer()
        explainer.available = False
        result = explainer.extract_scenario_from_text(
            "We're a fintech startup processing 10M transactions per day"
        )
        assert result == {}

    def test_build_explain_prompt_includes_scenario_data(self):
        prompt = BedrockExplainer._build_explain_prompt(
            _make_result(), _SCENARIO, impact=None,
        )
        assert "FINTECH" in prompt
        assert "5,000,000" in prompt
        assert "write_ahead_log" in prompt
        assert "high_write_volume" in prompt

    def test_build_explain_prompt_includes_impact_when_provided(self):
        from storage_advisor.estimation.impact_estimator import estimate_impact
        from storage_advisor.recommendation.recommendation_engine import run_recommendation_engine

        result = run_recommendation_engine(_SCENARIO)
        impact = estimate_impact(_SCENARIO, result.recommendations)

        prompt = BedrockExplainer._build_explain_prompt(result, _SCENARIO, impact)
        assert "Model-based impact estimates" in prompt
        assert "reduction" in prompt
