"""Architecture Builder — maps technique recommendations to concrete AWS services.

Takes the recommendation engine's output and produces a concrete architecture:
which AWS services to use, how they map to workload domains, and what
configuration each one needs.
"""

from __future__ import annotations

from pydantic import BaseModel

from storage_advisor.domain.recommendations import RecommendationResult
from storage_advisor.domain.scenario import Scenario


class ArchitectureComponent(BaseModel):
    component_id: str
    component_type: str
    service: str
    workload_domain: str
    required_by: list[str]
    configuration_notes: list[str]
    priority: str


class ArchitectureOutput(BaseModel):
    components: list[ArchitectureComponent]
    summary: str


_SLOT_DEFAULTS: dict[str, dict[str, str]] = {
    "s3": {
        "component_id": "s3_object_store",
        "component_type": "object_store",
        "service": "Amazon S3",
        "workload_domain": "object",
    },
    "rds": {
        "component_id": "rds_postgresql",
        "component_type": "relational_db",
        "service": "Amazon RDS for PostgreSQL",
        "workload_domain": "transactional",
    },
    "cache": {
        "component_id": "elasticache_redis",
        "component_type": "cache",
        "service": "Amazon ElastiCache (Redis)",
        "workload_domain": "cache",
    },
    "archive": {
        "component_id": "s3_glacier",
        "component_type": "archive",
        "service": "Amazon S3 Glacier Deep Archive",
        "workload_domain": "archive",
    },
    "analytics": {
        "component_id": "analytics_store",
        "component_type": "analytics_store",
        "service": "Apache Parquet / DuckDB",
        "workload_domain": "analytics",
    },
}

# (slot_key, creates_component, config_note)
_TECHNIQUE_RULES: dict[str, tuple[str, bool, str]] = {
    "object_storage":       ("s3",        True,  "S3 Standard for hot object storage"),
    "tiered_storage":       ("s3",        True,  "Enable S3 Intelligent-Tiering or Glacier lifecycle rules"),
    "lifecycle_management": ("s3",        False, "Automate data transitions between tiers with S3 Lifecycle policies"),
    "deduplication":        ("s3",        False, "Enable server-side deduplication or content-addressed storage"),
    "chunking":             ("s3",        False, "Enable multipart upload and content-defined chunking"),
    "partitioning":         ("rds",       True,  "Enable table partitioning by date or ID range"),
    "sharding":             ("rds",       True,  "Implement application-level sharding with consistent hashing"),
    "indexing":             ("rds",       False, "Create targeted indexes on frequently queried columns"),
    "replication":          ("rds",       False, "Enable Multi-AZ deployment for high availability and automatic failover"),
    "materialized_views":   ("rds",       False, "Create materialized views for expensive pre-computed queries"),
    "query_optimization":   ("rds",       False, "Profile and optimize slow queries; review execution plans"),
    "schema_optimization":  ("rds",       False, "Review schema for denormalization opportunities based on query patterns"),
    "caching":              ("cache",     True,  "Configure TTL strategy for cache invalidation"),
    "archiving":            ("archive",   True,  "Set up lifecycle rules for automatic archival after retention period"),
    "columnar_storage":     ("analytics", True,  "Store analytical data in columnar format"),
    "parquet_format":       ("analytics", True,  "Use Parquet files for efficient analytical queries"),
    "data_aggregation":     ("analytics", False, "Build pre-aggregated summary tables for dashboards"),
    "compression":          ("primary",   False, "Enable lossless compression (gzip/zstd) for stored data"),
    "data_pruning":         ("primary",   False, "Implement data retention policies and automated pruning"),
}


class ArchitectureBuilder:

    def build(
        self, scenario: Scenario, result: RecommendationResult,
    ) -> ArchitectureOutput:
        rec_map = {r.technique_id: r.priority for r in result.recommendations}
        components: dict[str, ArchitectureComponent] = {}

        # Pass 1: techniques that create standalone components
        for tid in rec_map:
            rule = _TECHNIQUE_RULES.get(tid)
            if rule is None or not rule[1]:
                continue
            slot, _, note = rule
            self._ensure_slot(components, slot)
            components[slot].required_by.append(tid)
            components[slot].configuration_notes.append(note)

        # Pass 2: config-note-only techniques attach to existing components
        for tid in rec_map:
            rule = _TECHNIQUE_RULES.get(tid)
            if rule is None or rule[1]:
                continue
            slot, _, note = rule
            if slot == "primary":
                slot = self._resolve_primary(components)
                if slot is None:
                    continue
            if slot not in components:
                continue
            components[slot].required_by.append(tid)
            components[slot].configuration_notes.append(note)

        # Scenario overrides
        if "sharding" in rec_map and "rds" in components:
            components["rds"].service = "Amazon RDS for PostgreSQL (sharded)"

        if (
            scenario.expected_users > 5_000_000
            and "columnar_storage" in rec_map
            and "analytics" in components
        ):
            components["analytics"].service = "Amazon Redshift"

        if (
            any(c == "HIPAA" for c in scenario.compliance_requirements)
            and "cache" in components
        ):
            components["cache"].configuration_notes.append(
                "HIPAA compliance: use managed ElastiCache (not self-managed Redis)"
            )

        # Set priority per component
        for comp in components.values():
            has_required = any(
                rec_map.get(tid) == "REQUIRED" for tid in comp.required_by
            )
            comp.priority = "REQUIRED" if has_required else "RECOMMENDED"

        summary = self._build_summary(components)
        return ArchitectureOutput(
            components=list(components.values()),
            summary=summary,
        )

    @staticmethod
    def _ensure_slot(
        components: dict[str, ArchitectureComponent], slot: str,
    ) -> None:
        if slot in components:
            return
        d = _SLOT_DEFAULTS[slot]
        components[slot] = ArchitectureComponent(
            component_id=d["component_id"],
            component_type=d["component_type"],
            service=d["service"],
            workload_domain=d["workload_domain"],
            required_by=[],
            configuration_notes=[],
            priority="RECOMMENDED",
        )

    @staticmethod
    def _resolve_primary(
        components: dict[str, ArchitectureComponent],
    ) -> str | None:
        if "s3" in components:
            return "s3"
        if "rds" in components:
            return "rds"
        return None

    @staticmethod
    def _build_summary(components: dict[str, ArchitectureComponent]) -> str:
        parts: list[str] = []

        if "rds" in components:
            rds = components["rds"]
            if "sharding" in rds.required_by:
                parts.append("Relational (RDS PostgreSQL, sharded) for transactions")
            else:
                parts.append("Relational (RDS PostgreSQL) for transactions")

        if "s3" in components:
            s3 = components["s3"]
            if "tiered_storage" in s3.required_by:
                parts.append("S3 for object and tiered storage")
            else:
                parts.append("S3 for object storage")

        if "cache" in components:
            parts.append("ElastiCache for read caching")

        if "analytics" in components:
            if "Redshift" in components["analytics"].service:
                parts.append("Redshift for analytics")
            else:
                parts.append("Parquet/DuckDB for analytics")

        if "archive" in components:
            parts.append("Glacier Deep Archive for archival")

        if not parts:
            return "No concrete architecture components recommended."

        return ", ".join(parts) + "."
