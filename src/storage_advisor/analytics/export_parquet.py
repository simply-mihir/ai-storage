"""Parquet export — writes scenarios + recommendation results partitioned by business_domain."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

DEFAULT_SOURCE = "data/synthetic/scenarios.parquet"
DEFAULT_OUTPUT = "data/parquet"


def export(
    source_path: str = DEFAULT_SOURCE,
    output_dir: str = DEFAULT_OUTPUT,
) -> Path:
    """Export the DuckDB analytics store to partitioned Parquet files."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect()
    conn.execute(
        f"CREATE VIEW scenarios AS SELECT * FROM read_parquet('{source_path}')"
    )

    dest = str(out)
    conn.execute(f"""
        COPY (
            SELECT * FROM scenarios
        ) TO '{dest}'
        (FORMAT PARQUET, PARTITION_BY (domain), OVERWRITE_OR_IGNORE)
    """)

    partitions = list(out.rglob("*.parquet"))
    logger.info(
        "Exported %d partition files to %s", len(partitions), dest,
    )
    return out


def row_count(output_dir: str = DEFAULT_OUTPUT) -> int:
    """Count total rows across all partition files."""
    conn = duckdb.connect()
    out = Path(output_dir)
    parquet_files = list(out.rglob("*.parquet"))
    if not parquet_files:
        return 0
    glob_pattern = str(out / "**" / "*.parquet")
    result = conn.execute(
        f"SELECT count(*) FROM read_parquet('{glob_pattern}', hive_partitioning=true)"
    ).fetchone()
    return result[0] if result else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
    result_dir = export()
    total = row_count(str(result_dir))
    print(f"Exported {total} rows to {result_dir}")
