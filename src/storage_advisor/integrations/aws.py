"""AWS integration — S3 storage and relational metadata tracking."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa

from storage_advisor.domain.recommendations import RecommendationResult
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import ImpactReport

logger = logging.getLogger(__name__)

metadata = sa.MetaData()

scenario_runs = sa.Table(
    "scenario_runs",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("scenario_id", sa.String(36), nullable=False),
    sa.Column("engine_version", sa.String(20)),
    sa.Column("kb_version", sa.String(20)),
    sa.Column("domain", sa.String(50)),
    sa.Column("users", sa.BigInteger),
    sa.Column("daily_growth_gb", sa.Float),
    sa.Column("status", sa.String(20)),
    sa.Column("recommendation_count", sa.Integer),
    sa.Column("top_technique", sa.String(100)),
    sa.Column("storage_reduction_pct", sa.Float),
    sa.Column("cost_reduction_pct", sa.Float),
    sa.Column("created_at", sa.DateTime, default=datetime.now(timezone.utc)),
)

recommendation_runs = sa.Table(
    "recommendation_runs",
    metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column(
        "scenario_run_id",
        sa.String(36),
        sa.ForeignKey("scenario_runs.id"),
        nullable=False,
    ),
    sa.Column("technique_id", sa.String(100)),
    sa.Column("priority", sa.String(20)),
    sa.Column("alignment_score", sa.Float),
    sa.Column("created_at", sa.DateTime, default=datetime.now(timezone.utc)),
)


# ---------------------------------------------------------------------------
# S3Store
# ---------------------------------------------------------------------------


class S3Store:

    def __init__(
        self,
        bucket_name: str | None = None,
        prefix: str = "ai-data-architect/",
    ):
        self.bucket_name = bucket_name or os.environ.get("S3_BUCKET_NAME")
        self.prefix = prefix
        self.available = False
        self._client = None

        if not self.bucket_name:
            logger.warning("S3Store: no bucket name configured")
            return

        try:
            import boto3

            self._client = boto3.client("s3")
            self._client.meta.endpoint_url
            self.available = True
            logger.info(
                "S3Store ready (bucket=%s, prefix=%s)",
                self.bucket_name,
                self.prefix,
            )
        except Exception as e:
            logger.warning("S3Store unavailable: %s", e)

    def upload_parquet(
        self,
        local_path: str,
        s3_key: str | None = None,
    ) -> str | None:
        if not self.available:
            logger.warning("S3Store.upload_parquet: client unavailable")
            return None

        s3_key = s3_key or f"{self.prefix}synthetic/scenarios.parquet"
        path = Path(local_path)
        if not path.exists():
            logger.error("File not found: %s", local_path)
            return None

        try:
            size_mb = path.stat().st_size / (1024 * 1024)
            start = time.perf_counter()
            self._client.upload_file(str(path), self.bucket_name, s3_key)
            elapsed = time.perf_counter() - start
            uri = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(
                "Uploaded %s (%.1f MB) to %s in %.1f s",
                local_path,
                size_mb,
                uri,
                elapsed,
            )
            return uri
        except Exception as e:
            logger.error("S3 upload failed: %s", e)
            return None

    def save_scenario_result(
        self,
        scenario_id: str,
        result: dict,
    ) -> str | None:
        if not self.available:
            return None

        s3_key = f"{self.prefix}results/{scenario_id}.json"
        try:
            body = json.dumps(result, default=str).encode()
            self._client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=body,
                ContentType="application/json",
            )
            uri = f"s3://{self.bucket_name}/{s3_key}"
            logger.info("Saved result to %s", uri)
            return uri
        except Exception as e:
            logger.error("S3 save_scenario_result failed: %s", e)
            return None

    def get_scenario_result(self, scenario_id: str) -> dict | None:
        if not self.available:
            return None

        s3_key = f"{self.prefix}results/{scenario_id}.json"
        try:
            response = self._client.get_object(
                Bucket=self.bucket_name, Key=s3_key,
            )
            body = response["Body"].read().decode()
            return json.loads(body)
        except Exception as e:
            logger.error("S3 get_scenario_result failed: %s", e)
            return None


# ---------------------------------------------------------------------------
# MetadataStore
# ---------------------------------------------------------------------------


class MetadataStore:

    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or os.environ.get(
            "DATABASE_URL", "sqlite:///data/metadata.db",
        )
        self.backend = (
            "postgresql" if "postgresql" in self.db_url else "sqlite"
        )

        try:
            self._engine = sa.create_engine(self.db_url)
            metadata.create_all(self._engine)
            logger.info(
                "MetadataStore ready (backend=%s)", self.backend,
            )
        except Exception as e:
            logger.error("MetadataStore init failed: %s", e)
            self._engine = None

    def save_run(
        self,
        scenario: Scenario,
        result: RecommendationResult,
        impact: ImpactReport,
    ) -> str:
        if self._engine is None:
            return "unknown"

        run_id = str(uuid4())
        scenario_id = str(uuid4())
        now = datetime.now(timezone.utc)

        top_technique = (
            result.recommendations[0].technique_id
            if result.recommendations
            else ""
        )

        try:
            with self._engine.begin() as conn:
                conn.execute(
                    scenario_runs.insert().values(
                        id=run_id,
                        scenario_id=scenario_id,
                        engine_version=result.engine_version,
                        kb_version=result.knowledge_base_version,
                        domain=scenario.business_domain,
                        users=scenario.expected_users,
                        daily_growth_gb=scenario.daily_growth_gb,
                        status="completed",
                        recommendation_count=len(result.recommendations),
                        top_technique=top_technique,
                        storage_reduction_pct=impact.storage.estimated_reduction_pct,
                        cost_reduction_pct=impact.cost.estimated_savings_pct,
                        created_at=now,
                    )
                )
                for rec in result.recommendations:
                    conn.execute(
                        recommendation_runs.insert().values(
                            id=str(uuid4()),
                            scenario_run_id=run_id,
                            technique_id=rec.technique_id,
                            priority=rec.priority,
                            alignment_score=rec.alignment_score,
                            created_at=now,
                        )
                    )
            logger.info("Saved run %s (%d recs)", run_id, len(result.recommendations))
            return run_id
        except Exception as e:
            logger.error("MetadataStore.save_run failed: %s", e)
            return "unknown"

    def recent_runs(self, limit: int = 10) -> list[dict]:
        if self._engine is None:
            return []

        try:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    sa.select(scenario_runs)
                    .order_by(scenario_runs.c.created_at.desc())
                    .limit(limit)
                ).fetchall()
            return [dict(row._mapping) for row in rows]
        except Exception as e:
            logger.error("MetadataStore.recent_runs failed: %s", e)
            return []

    def domain_stats(self) -> dict:
        if self._engine is None:
            return {}

        try:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    sa.select(
                        scenario_runs.c.domain,
                        sa.func.count().label("run_count"),
                    ).group_by(scenario_runs.c.domain)
                ).fetchall()
            return {row.domain: row.run_count for row in rows}
        except Exception as e:
            logger.error("MetadataStore.domain_stats failed: %s", e)
            return {}
