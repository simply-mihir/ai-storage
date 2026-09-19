"""Tests for confidence band estimation."""

from __future__ import annotations

import pytest

from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.confidence import ConfidenceEstimator
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.recommendation.recommendation_engine import run_recommendation_engine


def _demo_scenario() -> Scenario:
    return Scenario(
        business_domain="E_COMMERCE",
        company_size="LARGE",
        expected_users=10_000_000,
        concurrent_users=500_000,
        current_storage_gb=5000,
        daily_growth_gb=300,
        data_types=["IMAGES", "TRANSACTIONS"],
        structured_data_pct=40,
        semi_structured_data_pct=10,
        unstructured_data_pct=50,
        read_intensity="HIGH",
        write_intensity="HIGH",
        access_pattern="MIXED",
        latency_requirement_ms=100,
        availability_requirement=99.99,
        rto_minutes=15,
        rpo_minutes=5,
        retention_years=7,
        budget_level="HIGH",
        analytics_required=True,
        real_time_processing_required=True,
        sensitive_data=True,
        encryption_required=True,
        compliance_requirements=["SOC2", "PCI_DSS"],
    )


@pytest.fixture
def banded():
    scenario = _demo_scenario()
    result = run_recommendation_engine(scenario)
    impact = estimate_impact(scenario, result.recommendations)
    conf = ConfidenceEstimator()
    return conf.estimate_with_bands(scenario, impact)


class TestConfidenceBands:
    def test_bands_are_valid_ranges(self, banded):
        for band in [banded.storage_band, banded.cost_band, banded.latency_band]:
            assert band.low >= 0
            assert band.high >= band.low
            assert band.sample_size > 0
            assert band.confidence_note != ""

    def test_similar_scenarios_found(self, banded):
        assert banded.storage_band.sample_size >= 10

    def test_bands_are_in_percent_range(self, banded):
        assert 0 <= banded.storage_band.low <= 100
        assert 0 <= banded.storage_band.high <= 100
        assert 0 <= banded.cost_band.low <= 100
        assert 0 <= banded.latency_band.high <= 100

    def test_disclaimer_non_empty(self, banded):
        assert len(banded.disclaimer) > 20
