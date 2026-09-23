"""Tests for the EDA module."""

import pytest

from storage_advisor.analytics.eda import (
    correlation_matrix,
    industry_category_heatdata,
    savings_distributions,
    technique_cooccurrence,
    technique_frequency,
)
from storage_advisor.analytics.generator import ScenarioGenerator

PARQUET = None


@pytest.fixture(scope="module", autouse=True)
def _generate_parquet(tmp_path_factory):
    global PARQUET
    out = tmp_path_factory.mktemp("eda")
    gen = ScenarioGenerator()
    PARQUET = gen.generate(n=200, seed=42, output_dir=str(out))


class TestTechniqueFrequency:
    def test_non_empty(self):
        result = technique_frequency(PARQUET)
        assert len(result) > 0

    def test_has_required_keys(self):
        result = technique_frequency(PARQUET)
        assert "technique_id" in result[0]
        assert "count" in result[0]

    def test_by_domain_adds_domain_key(self):
        result = technique_frequency(PARQUET, by_domain=True)
        assert len(result) > 0
        assert "domain" in result[0]

    def test_descending_order(self):
        result = technique_frequency(PARQUET)
        counts = [r["count"] for r in result]
        assert counts == sorted(counts, reverse=True)


class TestSavingsDistributions:
    def test_storage_non_empty(self):
        result = savings_distributions(PARQUET, metric="storage")
        assert len(result) > 0

    def test_cost_non_empty(self):
        result = savings_distributions(PARQUET, metric="cost")
        assert len(result) > 0

    def test_latency_non_empty(self):
        result = savings_distributions(PARQUET, metric="latency")
        assert len(result) > 0

    def test_shape_has_stats(self):
        result = savings_distributions(PARQUET, metric="storage")
        for key in ("mean", "median", "min", "max", "stddev", "n"):
            assert key in result[0]

    def test_invalid_metric_raises(self):
        with pytest.raises(ValueError, match="metric must be"):
            savings_distributions(PARQUET, metric="bogus")


class TestCorrelationMatrix:
    def test_returns_columns_and_data(self):
        result = correlation_matrix(PARQUET)
        assert "columns" in result
        assert "data" in result

    def test_square_shape(self):
        result = correlation_matrix(PARQUET)
        n = len(result["columns"])
        assert len(result["data"]) == n
        assert all(len(row) == n for row in result["data"])

    def test_diagonal_is_one(self):
        result = correlation_matrix(PARQUET)
        for i, row in enumerate(result["data"]):
            assert abs(row[i] - 1.0) < 0.01


class TestTechniqueCooccurrence:
    def test_non_empty(self):
        result = technique_cooccurrence(PARQUET)
        assert len(result) > 0

    def test_support_ordering(self):
        result = technique_cooccurrence(PARQUET)
        supports = [r["support"] for r in result]
        assert supports == sorted(supports, reverse=True)

    def test_higher_threshold_fewer_results(self):
        low = technique_cooccurrence(PARQUET, min_support=0.05)
        high = technique_cooccurrence(PARQUET, min_support=0.20)
        assert len(high) <= len(low)


class TestIndustryCategoryHeatdata:
    def test_non_empty(self):
        result = industry_category_heatdata(PARQUET)
        assert len(result["domains"]) > 0
        assert len(result["techniques"]) > 0

    def test_shape_matches(self):
        result = industry_category_heatdata(PARQUET)
        assert len(result["data"]) == len(result["domains"])
        assert all(len(row) == len(result["techniques"]) for row in result["data"])
