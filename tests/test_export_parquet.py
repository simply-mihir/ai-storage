"""Tests for the Parquet export module."""

import duckdb

from storage_advisor.analytics.export_parquet import export, row_count
from storage_advisor.analytics.generator import ScenarioGenerator


class TestParquetExport:

    def test_files_exist_after_run(self, tmp_path):
        src_dir = tmp_path / "src"
        gen = ScenarioGenerator()
        src_path = gen.generate(n=50, seed=7, output_dir=str(src_dir))

        out_dir = tmp_path / "parquet_out"
        export(source_path=src_path, output_dir=str(out_dir))

        parquet_files = list(out_dir.rglob("*.parquet"))
        assert len(parquet_files) > 0

    def test_row_counts_match(self, tmp_path):
        src_dir = tmp_path / "src"
        gen = ScenarioGenerator()
        src_path = gen.generate(n=50, seed=7, output_dir=str(src_dir))

        conn = duckdb.connect()
        original_count = conn.execute(
            f"SELECT count(*) FROM read_parquet('{src_path}')"
        ).fetchone()[0]

        out_dir = tmp_path / "parquet_out"
        export(source_path=src_path, output_dir=str(out_dir))

        exported_count = row_count(str(out_dir))
        assert exported_count == original_count

    def test_partitioned_by_domain(self, tmp_path):
        src_dir = tmp_path / "src"
        gen = ScenarioGenerator()
        src_path = gen.generate(n=50, seed=7, output_dir=str(src_dir))

        out_dir = tmp_path / "parquet_out"
        export(source_path=src_path, output_dir=str(out_dir))

        domain_dirs = [d for d in out_dir.iterdir() if d.is_dir()]
        assert len(domain_dirs) > 0
        assert all(d.name.startswith("domain=") for d in domain_dirs)
