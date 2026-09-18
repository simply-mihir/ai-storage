"""Tests for the Problem Detector — verify known scenarios trigger expected problems."""

from storage_advisor.domain.problems import ProblemId, ProblemSeverity
from storage_advisor.domain.scenario import Scenario
from storage_advisor.detection.problem_detector import detect_problems
from storage_advisor.profiling.workload_profiler import profile_workload


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


def _problem_ids(scenario: Scenario) -> set[str]:
    profile = profile_workload(scenario)
    problems = detect_problems(scenario, profile)
    return {p.problem_id for p in problems}


class TestProblemDetection:
    def test_moderate_storage_growth(self):
        ids = _problem_ids(_scenario(daily_growth_gb=300))
        assert ProblemId.MODERATE_STORAGE_GROWTH in ids

    def test_high_storage_growth(self):
        ids = _problem_ids(_scenario(daily_growth_gb=1000))
        assert ProblemId.HIGH_STORAGE_GROWTH in ids

    def test_extreme_storage_growth(self):
        ids = _problem_ids(_scenario(daily_growth_gb=3000))
        assert ProblemId.EXTREME_STORAGE_GROWTH in ids

    def test_low_growth_no_problem(self):
        ids = _problem_ids(_scenario(daily_growth_gb=1))
        assert ProblemId.MODERATE_STORAGE_GROWTH not in ids
        assert ProblemId.HIGH_STORAGE_GROWTH not in ids
        assert ProblemId.EXTREME_STORAGE_GROWTH not in ids

    def test_high_read_latency(self):
        ids = _problem_ids(_scenario(read_intensity="HIGH", latency_requirement_ms=50))
        assert ProblemId.HIGH_READ_LATENCY in ids

    def test_relaxed_latency_no_read_problem(self):
        ids = _problem_ids(_scenario(read_intensity="HIGH", latency_requirement_ms=1000))
        assert ProblemId.HIGH_READ_LATENCY not in ids

    def test_high_write_pressure(self):
        ids = _problem_ids(_scenario(write_intensity="HIGH"))
        assert ProblemId.HIGH_WRITE_PRESSURE in ids

    def test_large_unstructured_workload(self):
        ids = _problem_ids(_scenario(
            unstructured_data_pct=60, data_types=["IMAGES", "VIDEOS"],
            structured_data_pct=20, semi_structured_data_pct=20,
        ))
        assert ProblemId.LARGE_UNSTRUCTURED_OBJECT_WORKLOAD in ids

    def test_analytics_workload(self):
        ids = _problem_ids(_scenario(analytics_required=True, current_storage_gb=10_000))
        assert ProblemId.HIGH_ANALYTICS_WORKLOAD in ids

    def test_no_analytics_no_problem(self):
        ids = _problem_ids(_scenario(analytics_required=False, current_storage_gb=10_000))
        assert ProblemId.HIGH_ANALYTICS_WORKLOAD not in ids

    def test_long_term_retention(self):
        ids = _problem_ids(_scenario(retention_years=7))
        assert ProblemId.LONG_TERM_RETENTION in ids

    def test_short_retention_no_problem(self):
        ids = _problem_ids(_scenario(retention_years=0.5))
        assert ProblemId.LONG_TERM_RETENTION not in ids

    def test_hot_cold_mix(self):
        ids = _problem_ids(_scenario(retention_years=3, daily_growth_gb=10))
        assert ProblemId.HOT_COLD_DATA_MIX in ids

    def test_no_growth_no_hot_cold(self):
        ids = _problem_ids(_scenario(retention_years=5, daily_growth_gb=0))
        assert ProblemId.HOT_COLD_DATA_MIX not in ids

    def test_large_transactional(self):
        ids = _problem_ids(_scenario(
            data_types=["TRANSACTIONS"], current_storage_gb=5000
        ))
        assert ProblemId.LARGE_TRANSACTIONAL_DATASET in ids

    def test_small_transactional_no_problem(self):
        ids = _problem_ids(_scenario(
            data_types=["TRANSACTIONS"], current_storage_gb=100
        ))
        assert ProblemId.LARGE_TRANSACTIONAL_DATASET not in ids

    def test_high_availability(self):
        ids = _problem_ids(_scenario(availability_requirement=99.99))
        assert ProblemId.HIGH_AVAILABILITY_REQUIREMENT in ids

    def test_standard_availability_no_problem(self):
        ids = _problem_ids(_scenario(availability_requirement=95.0))
        assert ProblemId.HIGH_AVAILABILITY_REQUIREMENT not in ids

    def test_disaster_recovery(self):
        ids = _problem_ids(_scenario(rto_minutes=10, rpo_minutes=5))
        assert ProblemId.DISASTER_RECOVERY_REQUIREMENT in ids

    def test_relaxed_dr_no_problem(self):
        ids = _problem_ids(_scenario(rto_minutes=480, rpo_minutes=240))
        assert ProblemId.DISASTER_RECOVERY_REQUIREMENT not in ids

    def test_compliance_requirement(self):
        ids = _problem_ids(_scenario(compliance_requirements=["HIPAA"]))
        assert ProblemId.COMPLIANCE_REQUIREMENT in ids

    def test_no_compliance_no_problem(self):
        ids = _problem_ids(_scenario(compliance_requirements=["NONE"]))
        assert ProblemId.COMPLIANCE_REQUIREMENT not in ids

    def test_scalability_pressure(self):
        ids = _problem_ids(_scenario(
            expected_users=5_000_000, concurrent_users=100_000, daily_growth_gb=200
        ))
        assert ProblemId.SCALABILITY_PRESSURE in ids


class TestProblemSeverityOrdering:
    def test_critical_before_high(self):
        s = _scenario(availability_requirement=99.99, daily_growth_gb=3000)
        profile = profile_workload(s)
        problems = detect_problems(s, profile)
        severities = [p.severity for p in problems]
        assert severities[0] == ProblemSeverity.CRITICAL

    def test_high_before_medium(self):
        s = _scenario(
            daily_growth_gb=1000, retention_years=7,
            expected_users=5_000_000, concurrent_users=100_000,
        )
        profile = profile_workload(s)
        problems = detect_problems(s, profile)
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        indices = [severity_order[p.severity] for p in problems]
        assert indices == sorted(indices)


class TestProblemEvidence:
    def test_evidence_contains_source_values(self):
        s = _scenario(daily_growth_gb=300)
        profile = profile_workload(s)
        problems = detect_problems(s, profile)
        growth_problem = next(
            p for p in problems if p.problem_id == ProblemId.MODERATE_STORAGE_GROWTH
        )
        assert growth_problem.evidence["daily_growth_gb"] == 300
        assert "daily_growth_gb" in growth_problem.source_fields
