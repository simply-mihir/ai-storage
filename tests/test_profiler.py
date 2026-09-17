"""Tests for the Workload Profiler — threshold boundary tests."""

import pytest

from storage_advisor.domain.scenario import Scenario
from storage_advisor.profiling.workload_profiler import (
    GROWTH_LOW_UPPER,
    GROWTH_MEDIUM_UPPER,
    LATENCY_LOW_UPPER,
    LATENCY_MODERATE_UPPER,
    LATENCY_ULTRA_LOW_UPPER,
    RETENTION_MEDIUM_UPPER,
    RETENTION_SHORT_UPPER,
    AVAIL_HIGH,
    AVAIL_MISSION_CRITICAL,
    AVAIL_VERY_HIGH,
    GrowthClass,
    LatencyClass,
    PressureLevel,
    RetentionClass,
    AvailabilityClass,
    CompliancePresence,
    profile_workload,
)


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


class TestStorageGrowthClassification:
    def test_low_growth(self):
        p = profile_workload(_scenario(daily_growth_gb=GROWTH_LOW_UPPER))
        assert p.storage_growth == GrowthClass.LOW

    def test_medium_growth_boundary(self):
        p = profile_workload(_scenario(daily_growth_gb=GROWTH_LOW_UPPER + 0.1))
        assert p.storage_growth == GrowthClass.MEDIUM

    def test_high_growth_boundary(self):
        p = profile_workload(_scenario(daily_growth_gb=GROWTH_MEDIUM_UPPER + 0.1))
        assert p.storage_growth == GrowthClass.HIGH

    def test_zero_growth(self):
        p = profile_workload(_scenario(daily_growth_gb=0))
        assert p.storage_growth == GrowthClass.LOW


class TestLatencyClassification:
    def test_ultra_low(self):
        p = profile_workload(_scenario(latency_requirement_ms=LATENCY_ULTRA_LOW_UPPER))
        assert p.latency_class == LatencyClass.ULTRA_LOW_LATENCY

    def test_low_latency(self):
        p = profile_workload(_scenario(latency_requirement_ms=LATENCY_ULTRA_LOW_UPPER + 1))
        assert p.latency_class == LatencyClass.LOW_LATENCY

    def test_moderate(self):
        p = profile_workload(_scenario(latency_requirement_ms=LATENCY_LOW_UPPER + 1))
        assert p.latency_class == LatencyClass.MODERATE

    def test_relaxed(self):
        p = profile_workload(_scenario(latency_requirement_ms=LATENCY_MODERATE_UPPER + 1))
        assert p.latency_class == LatencyClass.RELAXED


class TestRetentionClassification:
    def test_short_term(self):
        p = profile_workload(_scenario(retention_years=RETENTION_SHORT_UPPER))
        assert p.retention_class == RetentionClass.SHORT_TERM

    def test_medium_term(self):
        p = profile_workload(_scenario(retention_years=RETENTION_SHORT_UPPER + 0.1))
        assert p.retention_class == RetentionClass.MEDIUM_TERM

    def test_long_term(self):
        p = profile_workload(_scenario(retention_years=RETENTION_MEDIUM_UPPER + 0.1))
        assert p.retention_class == RetentionClass.LONG_TERM


class TestAvailabilityClassification:
    def test_standard(self):
        p = profile_workload(_scenario(availability_requirement=98.0))
        assert p.availability_class == AvailabilityClass.STANDARD

    def test_high(self):
        p = profile_workload(_scenario(availability_requirement=AVAIL_HIGH))
        assert p.availability_class == AvailabilityClass.HIGH

    def test_very_high(self):
        p = profile_workload(_scenario(availability_requirement=AVAIL_VERY_HIGH))
        assert p.availability_class == AvailabilityClass.VERY_HIGH

    def test_mission_critical(self):
        p = profile_workload(_scenario(availability_requirement=AVAIL_MISSION_CRITICAL))
        assert p.availability_class == AvailabilityClass.MISSION_CRITICAL


class TestReadPressure:
    def test_high_intensity_means_high_pressure(self):
        p = profile_workload(_scenario(read_intensity="HIGH"))
        assert p.read_pressure == PressureLevel.HIGH

    def test_low_intensity_low_concurrent(self):
        p = profile_workload(_scenario(read_intensity="LOW", concurrent_users=100))
        assert p.read_pressure == PressureLevel.LOW

    def test_medium_intensity_high_concurrent(self):
        p = profile_workload(_scenario(
            read_intensity="MEDIUM", concurrent_users=50_000, expected_users=100_000
        ))
        assert p.read_pressure == PressureLevel.HIGH


class TestCompliancePressure:
    def test_no_compliance(self):
        p = profile_workload(_scenario(compliance_requirements=["NONE"]))
        assert p.compliance_pressure == CompliancePresence.NONE

    def test_with_compliance(self):
        p = profile_workload(_scenario(compliance_requirements=["HIPAA"]))
        assert p.compliance_pressure == CompliancePresence.PRESENT

    def test_mixed_none_and_real(self):
        p = profile_workload(_scenario(compliance_requirements=["NONE", "GDPR"]))
        assert p.compliance_pressure == CompliancePresence.PRESENT


class TestObjectStoragePressure:
    def test_high_unstructured_with_matching_types(self):
        p = profile_workload(_scenario(
            unstructured_data_pct=60, data_types=["IMAGES", "DOCUMENTS"],
            structured_data_pct=20, semi_structured_data_pct=20,
        ))
        assert p.object_storage_pressure == PressureLevel.HIGH

    def test_no_unstructured(self):
        p = profile_workload(_scenario(
            unstructured_data_pct=0, data_types=["TRANSACTIONS"],
            structured_data_pct=100, semi_structured_data_pct=0,
        ))
        assert p.object_storage_pressure == PressureLevel.LOW

    def test_low_pct_but_unstructured_types(self):
        p = profile_workload(_scenario(
            unstructured_data_pct=10, data_types=["IMAGES"],
            structured_data_pct=80, semi_structured_data_pct=10,
        ))
        assert p.object_storage_pressure == PressureLevel.MEDIUM
