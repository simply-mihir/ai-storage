"""Tests for the WhatIfAnalyzer — scenario comparison through the full pipeline."""

from storage_advisor.analytics.whatif import WhatIfAnalyzer, WhatIfResult
from storage_advisor.domain.scenario import Scenario


def _demo(**overrides) -> Scenario:
    defaults = dict(
        business_domain="AI", company_size="ENTERPRISE",
        expected_users=10_000_000, concurrent_users=100_000,
        current_storage_gb=25_000, daily_growth_gb=300,
        data_types=["IMAGES", "DOCUMENTS", "TRANSACTIONS", "LOGS"],
        structured_data_pct=20, semi_structured_data_pct=20, unstructured_data_pct=60,
        read_intensity="HIGH", write_intensity="HIGH", access_pattern="MIXED",
        latency_requirement_ms=100, availability_requirement=99.99,
        rto_minutes=60, rpo_minutes=15,
        retention_years=7, budget_level="HIGH",
        analytics_required=True, real_time_processing_required=True,
        sensitive_data=True, encryption_required=True,
        compliance_requirements=["NONE"],
    )
    defaults.update(overrides)
    return Scenario(**defaults)


class TestGrowthChange:
    def test_produces_result(self):
        analyzer = WhatIfAnalyzer()
        result = analyzer.compare(
            baseline_scenario=_demo(daily_growth_gb=300),
            modified_scenario=_demo(daily_growth_gb=1000),
        )
        assert isinstance(result, WhatIfResult)

    def test_sharding_priority_changes(self):
        analyzer = WhatIfAnalyzer()
        result = analyzer.compare(
            baseline_scenario=_demo(daily_growth_gb=300),
            modified_scenario=_demo(daily_growth_gb=1000),
        )
        sharding_added = "sharding" in result.added_techniques
        sharding_changed = any(
            c["technique_id"] == "sharding" for c in result.changed_priorities
        )
        assert sharding_added or sharding_changed, (
            f"Expected sharding in added or changed_priorities. "
            f"added={result.added_techniques}, changed={result.changed_priorities}"
        )

    def test_impact_or_priorities_differ(self):
        analyzer = WhatIfAnalyzer()
        result = analyzer.compare(
            baseline_scenario=_demo(daily_growth_gb=300),
            modified_scenario=_demo(daily_growth_gb=1000),
        )
        impact_differs = (
            result.baseline_impact.storage.estimated_reduction_pct
            != result.modified_impact.storage.estimated_reduction_pct
            or result.baseline_impact.cost.estimated_savings_pct
            != result.modified_impact.cost.estimated_savings_pct
            or result.baseline_impact.latency.estimated_improvement_pct
            != result.modified_impact.latency.estimated_improvement_pct
        )
        priorities_differ = len(result.changed_priorities) > 0
        assert impact_differs or priorities_differ


class TestDomainOnlyChange:
    def test_minimal_technique_difference(self):
        analyzer = WhatIfAnalyzer()
        result = analyzer.compare(
            baseline_scenario=_demo(business_domain="AI"),
            modified_scenario=_demo(business_domain="FINTECH"),
        )
        assert len(result.added_techniques) <= 2
        assert len(result.removed_techniques) <= 2

    def test_summary_is_nonempty(self):
        analyzer = WhatIfAnalyzer()
        result = analyzer.compare(
            baseline_scenario=_demo(business_domain="AI"),
            modified_scenario=_demo(business_domain="FINTECH"),
        )
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
