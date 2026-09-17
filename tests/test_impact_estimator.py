"""Tests for the Impact Estimator — verify estimates and assumptions."""

from storage_advisor.domain.recommendations import Priority, Recommendation
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import estimate_impact


def _scenario(**overrides) -> Scenario:
    defaults = dict(
        business_domain="AI", company_size="STARTUP",
        expected_users=1000, concurrent_users=100,
        current_storage_gb=10_000.0, daily_growth_gb=100.0,
        data_types=["TEXT", "IMAGES"],
        structured_data_pct=50.0, semi_structured_data_pct=20.0, unstructured_data_pct=30.0,
        read_intensity="HIGH", write_intensity="MEDIUM", access_pattern="MIXED",
        latency_requirement_ms=100.0, availability_requirement=99.9,
        rto_minutes=60.0, rpo_minutes=15.0,
        retention_years=3.0, budget_level="MEDIUM",
        analytics_required=True, real_time_processing_required=False,
        sensitive_data=False, encryption_required=False,
        compliance_requirements=["NONE"],
    )
    defaults.update(overrides)
    return Scenario(**defaults)


def _make_rec(technique_id: str, **kwargs) -> Recommendation:
    defaults = dict(
        technique_id=technique_id,
        technique_name=technique_id.replace("_", " ").title(),
        category="STORAGE",
        priority=Priority.RECOMMENDED,
        alignment_score=0.5,
        problems_solved=["HIGH_STORAGE_GROWTH"],
        rationale="Test",
        evidence=[],
        benefits=[],
        disadvantages=[],
        implementation_complexity="MEDIUM",
        prerequisites=[],
        conflicts_with=[],
        conditions=[],
    )
    defaults.update(kwargs)
    return Recommendation(**defaults)


class TestStorageEstimation:
    def test_compression_reduces_storage(self):
        recs = [_make_rec("compression")]
        impact = estimate_impact(_scenario(), recs)
        assert impact.storage.estimated_reduction_gb > 0
        assert impact.storage.estimated_reduction_pct > 0

    def test_no_techniques_no_reduction(self):
        impact = estimate_impact(_scenario(), [])
        assert impact.storage.estimated_reduction_gb == 0
        assert impact.storage.estimated_reduction_pct == 0

    def test_multiple_techniques_compound(self):
        recs = [_make_rec("compression"), _make_rec("deduplication")]
        impact = estimate_impact(_scenario(), recs)
        # compound effect should be > single technique
        single = estimate_impact(_scenario(), [_make_rec("compression")])
        assert impact.storage.estimated_reduction_pct > single.storage.estimated_reduction_pct

    def test_label_is_model_based(self):
        impact = estimate_impact(_scenario(), [_make_rec("compression")])
        assert impact.storage.label == "MODEL-BASED ESTIMATE"


class TestCostEstimation:
    def test_tiered_storage_reduces_cost(self):
        recs = [_make_rec("tiered_storage")]
        impact = estimate_impact(_scenario(), recs)
        assert impact.cost.estimated_monthly_savings_usd > 0

    def test_baseline_cost_is_positive(self):
        impact = estimate_impact(_scenario(), [])
        assert impact.cost.estimated_monthly_baseline_usd > 0

    def test_assumptions_are_present(self):
        recs = [_make_rec("tiered_storage")]
        impact = estimate_impact(_scenario(), recs)
        assert len(impact.cost.assumptions) > 0


class TestLatencyEstimation:
    def test_caching_improves_latency(self):
        recs = [_make_rec("caching")]
        impact = estimate_impact(_scenario(), recs)
        assert impact.latency.estimated_improvement_pct > 0
        assert impact.latency.estimated_optimized_latency_ms < 100.0

    def test_indexing_improves_latency(self):
        recs = [_make_rec("indexing")]
        impact = estimate_impact(_scenario(), recs)
        assert impact.latency.estimated_improvement_pct > 0

    def test_no_perf_techniques_no_change(self):
        recs = [_make_rec("archiving")]
        impact = estimate_impact(_scenario(), recs)
        assert impact.latency.estimated_improvement_pct == 0.0


class TestDisclaimer:
    def test_disclaimer_present(self):
        impact = estimate_impact(_scenario(), [])
        assert "model-based" in impact.disclaimer.lower()
