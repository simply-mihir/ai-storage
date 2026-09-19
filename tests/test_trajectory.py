"""Tests for the Growth Trajectory Simulator."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from storage_advisor.analytics.trajectory import GrowthTrajectorySimulator
from storage_advisor.domain.scenario import Scenario


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


class TestSimulationCompletes:
    def test_simulation_completes(self):
        result = GrowthTrajectorySimulator().simulate(_demo_scenario(), months=6)
        assert len(result.snapshots) == 6
        assert result.months_simulated == 6

    def test_storage_grows_monotonically(self):
        result = GrowthTrajectorySimulator().simulate(_demo_scenario(), months=12)
        storages = [s.storage_gb for s in result.snapshots]
        assert all(storages[i] < storages[i + 1] for i in range(len(storages) - 1))

    def test_costs_are_positive(self):
        result = GrowthTrajectorySimulator().simulate(_demo_scenario(), months=6)
        assert all(s.real_cost_usd > 0 for s in result.snapshots)

    def test_tipping_points_are_in_order(self):
        result = GrowthTrajectorySimulator().simulate(_demo_scenario(), months=24)
        months = [tp.month for tp in result.tipping_points]
        assert months == sorted(months)

    def test_no_duplicate_tipping_points(self):
        result = GrowthTrajectorySimulator().simulate(_demo_scenario(), months=24)
        pairs = [(tp.technique_id, tp.severity) for tp in result.tipping_points]
        assert len(pairs) == len(set(pairs))

    def test_summary_is_non_empty(self):
        result = GrowthTrajectorySimulator().simulate(_demo_scenario(), months=6)
        assert len(result.summary) > 50

    def test_high_growth_produces_tipping_points(self):
        result = GrowthTrajectorySimulator().simulate(_demo_scenario(), months=24)
        assert len(result.tipping_points) > 0

    def test_daily_growth_scales_with_users(self):
        result = GrowthTrajectorySimulator().simulate(_demo_scenario(), months=12)
        month_1 = result.snapshots[0]
        month_12 = result.snapshots[11]
        assert month_12.daily_growth_gb > month_1.daily_growth_gb
        assert month_12.daily_growth_gb > 500


class TestTrajectoryAPI:
    def setup_method(self):
        from storage_advisor.app.api import app
        self.client = TestClient(app)

    def test_api_trajectory_endpoint(self):
        scenario = _demo_scenario().model_dump()
        resp = self.client.post(
            "/api/v1/trajectory",
            json={"scenario": scenario, "months": 6},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["tipping_points"], list)
        assert len(data["summary"]) > 0
        assert len(data["snapshots"]) == 6
