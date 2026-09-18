"""Analytics Store — DuckDB-backed query layer over the synthetic Parquet dataset."""

from __future__ import annotations

import duckdb
import pandas as pd


class AnalyticsStore:

    def __init__(self, parquet_path: str = "data/synthetic/scenarios.parquet"):
        self._conn = duckdb.connect()
        self._conn.execute(
            f"CREATE VIEW scenarios AS SELECT * FROM read_parquet('{parquet_path}')"
        )

    def query(self, sql: str) -> pd.DataFrame:
        return self._conn.execute(sql).df()

    def technique_frequency(self) -> pd.DataFrame:
        return self.query("""
            WITH exploded AS (
                SELECT unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id
                FROM scenarios
            )
            SELECT
                technique_id,
                count(*) AS recommendation_count,
                round(count(*) * 100.0 / (SELECT count(*) FROM scenarios), 1) AS pct_of_scenarios
            FROM exploded
            GROUP BY technique_id
            ORDER BY recommendation_count DESC
        """)

    def technique_frequency_by_domain(self) -> pd.DataFrame:
        return self.query("""
            WITH exploded AS (
                SELECT
                    domain,
                    unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id
                FROM scenarios
            )
            SELECT domain, technique_id, count(*) AS count
            FROM exploded
            GROUP BY domain, technique_id
            ORDER BY domain, count DESC
        """)

    def savings_by_technique(self) -> pd.DataFrame:
        return self.query("""
            WITH exploded AS (
                SELECT
                    unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id,
                    storage_reduction_pct,
                    cost_reduction_pct,
                    latency_improvement_pct
                FROM scenarios
            )
            SELECT
                technique_id,
                round(avg(storage_reduction_pct), 2) AS avg_storage_reduction,
                round(avg(cost_reduction_pct), 2) AS avg_cost_reduction,
                round(avg(latency_improvement_pct), 2) AS avg_latency_improvement,
                count(*) AS scenario_count
            FROM exploded
            GROUP BY technique_id
            ORDER BY avg_storage_reduction DESC
        """)

    def technique_cooccurrence(self) -> pd.DataFrame:
        return self.query("""
            WITH exploded AS (
                SELECT
                    scenario_id,
                    unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id
                FROM scenarios
            )
            SELECT
                a.technique_id AS technique_a,
                b.technique_id AS technique_b,
                count(*) AS cooccurrence_count
            FROM exploded a
            JOIN exploded b
                ON a.scenario_id = b.scenario_id
                AND a.technique_id < b.technique_id
            GROUP BY a.technique_id, b.technique_id
            ORDER BY cooccurrence_count DESC
        """)

    def domain_summary(self) -> pd.DataFrame:
        return self.query("""
            WITH exploded AS (
                SELECT
                    domain,
                    unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id
                FROM scenarios
            ),
            tech_counts AS (
                SELECT domain, technique_id, count(*) AS cnt
                FROM exploded
                GROUP BY domain, technique_id
            ),
            top_tech AS (
                SELECT domain, technique_id AS most_common_technique
                FROM (
                    SELECT domain, technique_id,
                           row_number() OVER (PARTITION BY domain ORDER BY cnt DESC) AS rn
                    FROM tech_counts
                )
                WHERE rn = 1
            )
            SELECT
                s.domain,
                count(*) AS scenario_count,
                round(avg(s.storage_reduction_pct), 2) AS avg_storage_reduction,
                round(avg(s.cost_reduction_pct), 2) AS avg_cost_reduction,
                round(avg(s.latency_improvement_pct), 2) AS avg_latency_improvement,
                t.most_common_technique
            FROM scenarios s
            JOIN top_tech t ON s.domain = t.domain
            GROUP BY s.domain, t.most_common_technique
            ORDER BY s.domain
        """)

    def outliers(
        self, metric: str = "storage_reduction_pct", top_n: int = 10,
    ) -> pd.DataFrame:
        return self.query(f"""
            SELECT
                scenario_id, domain, users, daily_growth_gb,
                {metric}, all_technique_ids, detected_problems
            FROM scenarios
            ORDER BY {metric} DESC
            LIMIT {top_n}
        """)

    def kpi_summary(self) -> dict:
        row = self.query("""
            WITH exploded AS (
                SELECT unnest(from_json(all_technique_ids, '["VARCHAR"]')) AS technique_id
                FROM scenarios
            ),
            top AS (
                SELECT technique_id, count(*) AS cnt
                FROM exploded
                GROUP BY technique_id
                ORDER BY cnt DESC
                LIMIT 1
            )
            SELECT
                (SELECT count(*) FROM scenarios) AS total_scenarios,
                (SELECT round(avg(storage_reduction_pct), 2) FROM scenarios) AS avg_storage_reduction_pct,
                (SELECT round(avg(cost_reduction_pct), 2) FROM scenarios) AS avg_cost_reduction_pct,
                (SELECT round(avg(latency_improvement_pct), 2) FROM scenarios) AS avg_latency_improvement_pct,
                (SELECT technique_id FROM top) AS most_recommended_technique,
                (SELECT count(DISTINCT domain) FROM scenarios) AS unique_domains,
                (SELECT round(
                    count(*) FILTER (WHERE has_sharding) * 100.0 / count(*), 2
                ) FROM scenarios) AS scenarios_with_sharding_pct
        """).iloc[0].to_dict()
        return row
