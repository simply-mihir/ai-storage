"""Tests for AWS integration — SQLite metadata (no AWS needed), S3 fallback."""

import os
import uuid

import pytest

from storage_advisor.domain.recommendations import (
    Priority,
    Recommendation,
    RecommendationResult,
    Strategy,
)
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.integrations.aws import MetadataStore, S3Store
from storage_advisor.recommendation.recommendation_engine import run_recommendation_engine

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
    compliance_requirements=["PCI_DSS", "SOC2"],
)


@pytest.fixture(scope="module")
def pipeline_result():
    result = run_recommendation_engine(_SCENARIO)
    impact = estimate_impact(_SCENARIO, result.recommendations)
    return result, impact


@pytest.fixture()
def meta_store(tmp_path):
    db_path = tmp_path / "test.db"
    return MetadataStore(db_url=f"sqlite:///{db_path}")


class TestMetadataStore:
    def test_save_run_returns_uuid(self, meta_store, pipeline_result):
        result, impact = pipeline_result
        run_id = meta_store.save_run(_SCENARIO, result, impact)
        assert isinstance(run_id, str)
        uuid.UUID(run_id)

    def test_recent_runs_returns_list(self, meta_store, pipeline_result):
        result, impact = pipeline_result
        meta_store.save_run(_SCENARIO, result, impact)
        runs = meta_store.recent_runs()
        assert isinstance(runs, list)
        assert len(runs) >= 1
        assert runs[0]["domain"] == "FINTECH"

    def test_domain_stats_returns_dict(self, meta_store, pipeline_result):
        result, impact = pipeline_result
        meta_store.save_run(_SCENARIO, result, impact)
        stats = meta_store.domain_stats()
        assert isinstance(stats, dict)
        assert "FINTECH" in stats
        assert stats["FINTECH"] >= 1

    def test_recent_runs_contains_expected_fields(self, meta_store, pipeline_result):
        result, impact = pipeline_result
        meta_store.save_run(_SCENARIO, result, impact)
        runs = meta_store.recent_runs()
        row = runs[0]
        for key in [
            "id", "scenario_id", "engine_version", "domain",
            "users", "recommendation_count", "top_technique",
            "storage_reduction_pct", "cost_reduction_pct",
        ]:
            assert key in row, f"Missing key: {key}"

    def test_backend_is_sqlite(self, meta_store):
        assert meta_store.backend == "sqlite"


class TestS3Store:
    def test_no_bucket_sets_unavailable(self):
        store = S3Store(bucket_name=None)
        assert store.available is False

    def test_upload_returns_none_when_unavailable(self, tmp_path):
        store = S3Store(bucket_name=None)
        dummy = tmp_path / "test.parquet"
        dummy.write_bytes(b"fake")
        result = store.upload_parquet(str(dummy))
        assert result is None

    def test_save_scenario_result_returns_none_when_unavailable(self):
        store = S3Store(bucket_name=None)
        result = store.save_scenario_result("test-id", {"key": "value"})
        assert result is None

    def test_get_scenario_result_returns_none_when_unavailable(self):
        store = S3Store(bucket_name=None)
        result = store.get_scenario_result("test-id")
        assert result is None
