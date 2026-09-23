"""EDA module — pure functions over the DuckDB analytics store."""

from __future__ import annotations

import duckdb


def _conn(parquet_path: str = "data/synthetic/scenarios.parquet") -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect()
    conn.execute(
        f"CREATE VIEW scenarios AS SELECT * FROM read_parquet('{parquet_path}')"
    )
    return conn


def technique_frequency(
    parquet_path: str = "data/synthetic/scenarios.parquet",
    *,
    by_domain: bool = False,
) -> list[dict]:
    """Technique recommendation frequency, optionally grouped by domain."""
    conn = _conn(parquet_path)
    if by_domain:
        df = conn.execute("""
            WITH exploded AS (
                SELECT
                    domain,
                    unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id
                FROM scenarios
            )
            SELECT domain, technique_id, count(*) AS count,
                   round(count(*) * 100.0 /
                         (SELECT count(*) FROM scenarios), 1) AS pct
            FROM exploded
            GROUP BY domain, technique_id
            ORDER BY domain, count DESC
        """).df()
    else:
        df = conn.execute("""
            WITH exploded AS (
                SELECT unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id
                FROM scenarios
            )
            SELECT technique_id,
                   count(*) AS count,
                   round(count(*) * 100.0 /
                         (SELECT count(*) FROM scenarios), 1) AS pct
            FROM exploded
            GROUP BY technique_id
            ORDER BY count DESC
        """).df()
    return df.to_dict(orient="records")


def savings_distributions(
    parquet_path: str = "data/synthetic/scenarios.parquet",
    metric: str = "storage",
) -> list[dict]:
    """Distribution of savings for a given metric (storage/cost/latency)."""
    col_map = {
        "storage": "storage_reduction_pct",
        "cost": "cost_reduction_pct",
        "latency": "latency_improvement_pct",
    }
    col = col_map.get(metric)
    if col is None:
        msg = f"metric must be one of {list(col_map)}"
        raise ValueError(msg)
    conn = _conn(parquet_path)
    df = conn.execute(f"""
        SELECT
            domain,
            round(avg({col}), 2) AS mean,
            round(median({col}), 2) AS median,
            round(min({col}), 2) AS min,
            round(max({col}), 2) AS max,
            round(stddev({col}), 2) AS stddev,
            count(*) AS n
        FROM scenarios
        GROUP BY domain
        ORDER BY mean DESC
    """).df()
    return df.to_dict(orient="records")


def correlation_matrix(
    parquet_path: str = "data/synthetic/scenarios.parquet",
) -> dict:
    """Correlation of profile numeric features vs savings targets."""
    conn = _conn(parquet_path)
    df = conn.execute("""
        SELECT
            users, concurrent_users, storage_size_gb, daily_growth_gb,
            latency_ms, availability_pct, rto_hours, rpo_hours,
            retention_years,
            storage_reduction_pct, cost_reduction_pct, latency_improvement_pct
        FROM scenarios
    """).df()
    corr = df.corr(numeric_only=True)
    return {
        "columns": corr.columns.tolist(),
        "data": corr.round(3).values.tolist(),
    }


def technique_cooccurrence(
    parquet_path: str = "data/synthetic/scenarios.parquet",
    min_support: float = 0.05,
) -> list[dict]:
    """Technique co-occurrence itemsets above min_support threshold."""
    conn = _conn(parquet_path)
    total = conn.execute("SELECT count(*) FROM scenarios").fetchone()[0]
    min_count = int(total * min_support)
    df = conn.execute(f"""
        WITH exploded AS (
            SELECT
                scenario_id,
                unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id
            FROM scenarios
        )
        SELECT
            a.technique_id AS technique_a,
            b.technique_id AS technique_b,
            count(*) AS cooccurrence_count,
            round(count(*) * 1.0 / {total}, 4) AS support
        FROM exploded a
        JOIN exploded b
            ON a.scenario_id = b.scenario_id
            AND a.technique_id < b.technique_id
        GROUP BY a.technique_id, b.technique_id
        HAVING count(*) >= {min_count}
        ORDER BY support DESC
    """).df()
    return df.to_dict(orient="records")


def industry_category_heatdata(
    parquet_path: str = "data/synthetic/scenarios.parquet",
) -> dict:
    """Industry (domain) x average storage savings heatmap data."""
    conn = _conn(parquet_path)
    df = conn.execute("""
        WITH exploded AS (
            SELECT
                domain,
                unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id,
                storage_reduction_pct
            FROM scenarios
        )
        SELECT
            domain,
            technique_id,
            round(avg(storage_reduction_pct), 2) AS avg_storage_savings
        FROM exploded
        GROUP BY domain, technique_id
        ORDER BY domain, avg_storage_savings DESC
    """).df()
    pivot = df.pivot_table(
        index="domain",
        columns="technique_id",
        values="avg_storage_savings",
        fill_value=0,
    )
    return {
        "domains": pivot.index.tolist(),
        "techniques": pivot.columns.tolist(),
        "data": pivot.round(2).values.tolist(),
    }
