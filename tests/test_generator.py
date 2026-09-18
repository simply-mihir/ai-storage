"""Tests for the synthetic scenario generator."""

from pathlib import Path

import pandas as pd

from storage_advisor.analytics.generator import ScenarioGenerator


REQUIRED_COLUMNS = [
    "scenario_id", "domain", "users", "concurrent_users", "storage_size_gb",
    "daily_growth_gb", "data_types", "read_intensity", "write_intensity",
    "latency_ms", "availability_pct", "rto_hours", "rpo_hours",
    "retention_years", "compliance", "analytics_flag", "budget_tier",
    "profile_read_category", "profile_write_category",
    "profile_growth_category", "profile_scale_category",
    "detected_problems", "problem_count", "has_high_availability_req",
    "has_high_growth", "has_cost_pressure",
    "all_technique_ids", "required_technique_ids", "recommendation_count",
    "top_technique", "has_caching", "has_partitioning", "has_sharding",
    "has_tiered_storage", "has_object_storage", "has_columnar",
    "baseline_storage_gb", "optimized_storage_gb", "storage_reduction_pct",
    "baseline_cost_usd", "optimized_cost_usd", "cost_reduction_pct",
    "baseline_latency_ms", "optimized_latency_ms", "latency_improvement_pct",
    "architecture_services", "component_count",
]


class TestScenarioGenerator:

    def test_generates_without_error(self, tmp_path):
        gen = ScenarioGenerator()
        path = gen.generate(n=50, seed=42, output_dir=str(tmp_path))
        assert Path(path).exists()

    def test_returns_valid_path(self, tmp_path):
        gen = ScenarioGenerator()
        path = gen.generate(n=50, seed=42, output_dir=str(tmp_path))
        assert path.endswith(".parquet")
        assert Path(path).stat().st_size > 0

    def test_minimum_row_count(self, tmp_path):
        gen = ScenarioGenerator()
        path = gen.generate(n=50, seed=42, output_dir=str(tmp_path))
        df = pd.read_parquet(path)
        assert len(df) >= 45

    def test_all_required_columns_present(self, tmp_path):
        gen = ScenarioGenerator()
        path = gen.generate(n=50, seed=42, output_dir=str(tmp_path))
        df = pd.read_parquet(path)
        for col in REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_no_nulls_in_required_fields(self, tmp_path):
        gen = ScenarioGenerator()
        path = gen.generate(n=50, seed=42, output_dir=str(tmp_path))
        df = pd.read_parquet(path)
        for col in ["scenario_id", "domain", "users", "storage_size_gb",
                     "recommendation_count", "storage_reduction_pct"]:
            assert df[col].notna().all(), f"Null values in {col}"

    def test_storage_reduction_in_range(self, tmp_path):
        gen = ScenarioGenerator()
        path = gen.generate(n=50, seed=42, output_dir=str(tmp_path))
        df = pd.read_parquet(path)
        assert (df["storage_reduction_pct"] >= 0).all()
        assert (df["storage_reduction_pct"] <= 100).all()

    def test_reproducibility(self, tmp_path):
        gen = ScenarioGenerator()
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        path_a = gen.generate(n=50, seed=42, output_dir=str(dir_a))
        path_b = gen.generate(n=50, seed=42, output_dir=str(dir_b))
        df_a = pd.read_parquet(path_a)
        df_b = pd.read_parquet(path_b)
        assert list(df_a["scenario_id"]) == list(df_b["scenario_id"])
