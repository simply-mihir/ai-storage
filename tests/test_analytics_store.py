"""Tests for the AnalyticsStore DuckDB query layer."""

import pytest

from storage_advisor.analytics.generator import ScenarioGenerator
from storage_advisor.analytics.store import AnalyticsStore


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    out = tmp_path_factory.mktemp("analytics")
    gen = ScenarioGenerator()
    path = gen.generate(n=100, seed=1, output_dir=str(out))
    return AnalyticsStore(parquet_path=path)


class TestTechniqueFrequency:
    def test_returns_19_rows(self, store):
        df = store.technique_frequency()
        assert len(df) == 19

    def test_pct_sums_above_100(self, store):
        df = store.technique_frequency()
        assert df["pct_of_scenarios"].sum() > 100


class TestTechniqueFrequencyByDomain:
    def test_has_domain_and_technique_columns(self, store):
        df = store.technique_frequency_by_domain()
        assert "domain" in df.columns
        assert "technique_id" in df.columns
        assert "count" in df.columns

    def test_rows_per_domain_per_technique(self, store):
        df = store.technique_frequency_by_domain()
        pairs = set(zip(df["domain"], df["technique_id"]))
        assert len(pairs) == len(df)


class TestSavingsByTechnique:
    def test_no_null_avg_values(self, store):
        df = store.savings_by_technique()
        assert df["avg_storage_reduction"].notna().all()
        assert df["avg_cost_reduction"].notna().all()
        assert df["avg_latency_improvement"].notna().all()


class TestCooccurrence:
    def test_no_self_pairs(self, store):
        df = store.technique_cooccurrence()
        assert (df["technique_a"] != df["technique_b"]).all()


class TestKpiSummary:
    def test_returns_all_keys(self, store):
        kpi = store.kpi_summary()
        expected_keys = [
            "total_scenarios", "avg_storage_reduction_pct",
            "avg_cost_reduction_pct", "avg_latency_improvement_pct",
            "most_recommended_technique", "unique_domains",
            "scenarios_with_sharding_pct",
        ]
        for key in expected_keys:
            assert key in kpi, f"Missing key: {key}"
            assert kpi[key] is not None, f"Null value for: {key}"
