"""Tests for the Recommendation Engine — end-to-end pipeline and rule behavior."""

import json

from storage_advisor.domain.problems import ProblemId
from storage_advisor.domain.recommendations import Priority
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.recommendation.recommendation_engine import run_recommendation_engine


def _scenario(**overrides) -> Scenario:
    defaults = dict(
        business_domain="AI", company_size="STARTUP",
        expected_users=1000, concurrent_users=100,
        current_storage_gb=100.0, daily_growth_gb=1.0,
        data_types=["TEXT"],
        structured_data_pct=100.0, semi_structured_data_pct=0.0, unstructured_data_pct=0.0,
        read_intensity="LOW", write_intensity="LOW", access_pattern="MIXED",
        latency_requirement_ms=1000.0, availability_requirement=95.0,
        rto_minutes=480.0, rpo_minutes=240.0,
        retention_years=0.5, budget_level="MEDIUM",
        analytics_required=False, real_time_processing_required=False,
        sensitive_data=False, encryption_required=False,
        compliance_requirements=["NONE"],
    )
    defaults.update(overrides)
    return Scenario(**defaults)


class TestEndToEndPipeline:
    def test_baseline_scenario_produces_recommendations(self):
        s = _scenario(
            expected_users=10_000_000, concurrent_users=100_000,
            current_storage_gb=25_000, daily_growth_gb=300,
            data_types=["IMAGES", "DOCUMENTS", "TRANSACTIONS", "LOGS"],
            structured_data_pct=20, semi_structured_data_pct=20, unstructured_data_pct=60,
            read_intensity="HIGH", write_intensity="HIGH",
            latency_requirement_ms=100, availability_requirement=99.99,
            rto_minutes=60, rpo_minutes=15,
            retention_years=7, analytics_required=True,
            real_time_processing_required=True,
            sensitive_data=True, encryption_required=True,
        )
        result = run_recommendation_engine(s)
        assert len(result.recommendations) > 0
        assert len(result.detected_problems) > 0
        assert result.engine_version == "1.0.0"

    def test_minimal_scenario_produces_fewer_recommendations(self):
        s = _scenario()
        result = run_recommendation_engine(s)
        assert len(result.recommendations) < 19

    def test_result_is_json_serializable(self):
        s = _scenario(
            expected_users=10_000_000, concurrent_users=100_000,
            current_storage_gb=25_000, daily_growth_gb=300,
            data_types=["IMAGES", "TRANSACTIONS"],
            structured_data_pct=40, semi_structured_data_pct=10, unstructured_data_pct=50,
            read_intensity="HIGH", write_intensity="HIGH",
            latency_requirement_ms=100, availability_requirement=99.99,
            rto_minutes=60, rpo_minutes=15,
            retention_years=7, analytics_required=True,
        )
        result = run_recommendation_engine(s)
        json_str = result.model_dump_json()
        parsed = json.loads(json_str)
        assert "recommendations" in parsed
        assert "strategy" in parsed
        assert "detected_problems" in parsed


class TestRecommendationPriority:
    def test_replication_required_for_mission_critical(self):
        s = _scenario(availability_requirement=99.99)
        result = run_recommendation_engine(s)
        replication = next(
            (r for r in result.recommendations if r.technique_id == "replication"),
            None,
        )
        assert replication is not None
        assert replication.priority == Priority.REQUIRED

    def test_caching_recommended_for_read_heavy_low_latency(self):
        s = _scenario(
            read_intensity="HIGH", latency_requirement_ms=50,
            expected_users=1_000_000, concurrent_users=50_000,
        )
        result = run_recommendation_engine(s)
        caching = next(
            (r for r in result.recommendations if r.technique_id == "caching"),
            None,
        )
        assert caching is not None
        assert caching.priority in (Priority.REQUIRED, Priority.RECOMMENDED)


class TestStrategyGrouping:
    def test_strategy_buckets_populated(self):
        s = _scenario(
            expected_users=10_000_000, concurrent_users=100_000,
            current_storage_gb=25_000, daily_growth_gb=300,
            data_types=["IMAGES", "TRANSACTIONS"],
            structured_data_pct=40, semi_structured_data_pct=10, unstructured_data_pct=50,
            read_intensity="HIGH", write_intensity="HIGH",
            latency_requirement_ms=100, availability_requirement=99.99,
            rto_minutes=60, rpo_minutes=15,
            retention_years=7, analytics_required=True,
        )
        result = run_recommendation_engine(s)
        strategy = result.strategy
        assert len(strategy.transactional) > 0
        assert len(strategy.object_storage) > 0
        assert len(strategy.caching) > 0
        assert len(strategy.archival) > 0
        assert len(strategy.security) > 0


class TestConflictResolution:
    def test_sharding_requires_partitioning(self):
        """If partitioning is somehow removed, sharding should also be removed."""
        techniques = load_techniques()
        # Remove partitioning from the KB
        filtered_techniques = [t for t in techniques if t.id != "partitioning"]
        s = _scenario(
            expected_users=10_000_000, concurrent_users=100_000,
            current_storage_gb=25_000, daily_growth_gb=300,
            write_intensity="HIGH",
            data_types=["TRANSACTIONS"],
        )
        result = run_recommendation_engine(s, techniques=filtered_techniques)
        rec_ids = {r.technique_id for r in result.recommendations}
        assert "sharding" not in rec_ids

    def test_lifecycle_requires_tiered_storage(self):
        """Lifecycle management should be dropped if tiered storage is absent."""
        techniques = load_techniques()
        filtered = [t for t in techniques if t.id != "tiered_storage"]
        s = _scenario(retention_years=7, daily_growth_gb=200)
        result = run_recommendation_engine(s, techniques=filtered)
        rec_ids = {r.technique_id for r in result.recommendations}
        assert "lifecycle_management" not in rec_ids


class TestHardConstraints:
    def test_dedup_excluded_for_tiny_dataset(self):
        s = _scenario(current_storage_gb=50, daily_growth_gb=200)
        result = run_recommendation_engine(s)
        rec_ids = {r.technique_id for r in result.recommendations}
        assert "deduplication" not in rec_ids


class TestRecommendationContent:
    def test_every_recommendation_has_rationale(self):
        s = _scenario(
            expected_users=10_000_000, concurrent_users=100_000,
            current_storage_gb=25_000, daily_growth_gb=300,
            data_types=["IMAGES", "TRANSACTIONS"],
            structured_data_pct=40, semi_structured_data_pct=10, unstructured_data_pct=50,
            read_intensity="HIGH", write_intensity="HIGH",
            latency_requirement_ms=100, availability_requirement=99.99,
            retention_years=7, analytics_required=True,
        )
        result = run_recommendation_engine(s)
        for rec in result.recommendations:
            assert rec.rationale, f"{rec.technique_id} has no rationale"
            assert len(rec.evidence) > 0, f"{rec.technique_id} has no evidence"
            assert len(rec.problems_solved) > 0, f"{rec.technique_id} solves no problems"

    def test_assumptions_present(self):
        s = _scenario()
        result = run_recommendation_engine(s)
        assert len(result.assumptions) > 0


class TestImpactEstimation:
    def test_impact_report_has_all_sections(self):
        s = _scenario(
            current_storage_gb=25_000, daily_growth_gb=300,
            data_types=["IMAGES", "TRANSACTIONS"],
            structured_data_pct=40, semi_structured_data_pct=10, unstructured_data_pct=50,
            read_intensity="HIGH", latency_requirement_ms=100,
            availability_requirement=99.99, retention_years=7,
            expected_users=10_000_000, concurrent_users=100_000,
            write_intensity="HIGH", analytics_required=True,
        )
        result = run_recommendation_engine(s)
        impact = estimate_impact(s, result.recommendations)
        assert impact.storage.current_storage_gb == 25_000
        assert impact.storage.estimated_reduction_gb > 0
        assert impact.cost.estimated_monthly_savings_usd > 0
        assert impact.latency.estimated_improvement_pct > 0
        assert impact.storage.label == "MODEL-BASED ESTIMATE"
        assert len(impact.storage.assumptions) > 0

    def test_no_performance_techniques_no_latency_change(self):
        s = _scenario(retention_years=7, daily_growth_gb=200)
        result = run_recommendation_engine(s)
        # Filter to only non-performance recommendations
        rec_ids = {r.technique_id for r in result.recommendations}
        has_perf = any(rid in rec_ids for rid in ["caching", "indexing", "partitioning"])
        impact = estimate_impact(s, result.recommendations)
        if not has_perf:
            assert impact.latency.estimated_improvement_pct == 0.0


class TestAllSampleScenarios:
    """Run all 6 sample scenarios and verify they complete without errors."""

    def test_all_samples_produce_results(self):
        import json
        from pathlib import Path

        samples_path = Path(__file__).resolve().parents[1] / "examples" / "sample_scenarios.json"
        data = json.loads(samples_path.read_text())

        for entry in data["scenarios"]:
            name = entry["name"]
            scenario = Scenario(**entry["scenario"])
            result = run_recommendation_engine(scenario)
            impact = estimate_impact(scenario, result.recommendations)

            assert len(result.detected_problems) > 0, f"{name}: no problems detected"
            assert len(result.recommendations) > 0, f"{name}: no recommendations"
            assert impact.storage.current_storage_gb > 0, f"{name}: bad storage estimate"
