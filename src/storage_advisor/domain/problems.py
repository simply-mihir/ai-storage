"""Problem domain model — architectural pressures detected from a workload scenario."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ProblemSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ProblemId(StrEnum):
    MODERATE_STORAGE_GROWTH = "MODERATE_STORAGE_GROWTH"
    HIGH_STORAGE_GROWTH = "HIGH_STORAGE_GROWTH"
    EXTREME_STORAGE_GROWTH = "EXTREME_STORAGE_GROWTH"
    HIGH_READ_LATENCY = "HIGH_READ_LATENCY"
    HIGH_WRITE_PRESSURE = "HIGH_WRITE_PRESSURE"
    LARGE_UNSTRUCTURED_OBJECT_WORKLOAD = "LARGE_UNSTRUCTURED_OBJECT_WORKLOAD"
    HIGH_ANALYTICS_WORKLOAD = "HIGH_ANALYTICS_WORKLOAD"
    LONG_TERM_RETENTION = "LONG_TERM_RETENTION"
    HOT_COLD_DATA_MIX = "HOT_COLD_DATA_MIX"
    LARGE_TRANSACTIONAL_DATASET = "LARGE_TRANSACTIONAL_DATASET"
    HIGH_AVAILABILITY_REQUIREMENT = "HIGH_AVAILABILITY_REQUIREMENT"
    DISASTER_RECOVERY_REQUIREMENT = "DISASTER_RECOVERY_REQUIREMENT"
    COMPLIANCE_REQUIREMENT = "COMPLIANCE_REQUIREMENT"
    SCALABILITY_PRESSURE = "SCALABILITY_PRESSURE"
    SECURITY_EXPOSURE = "SECURITY_EXPOSURE"
    COST_OVERRUN_RISK = "COST_OVERRUN_RISK"
    QUERY_PERFORMANCE_DEGRADATION = "QUERY_PERFORMANCE_DEGRADATION"
    MAINTENANCE_BURDEN = "MAINTENANCE_BURDEN"


class DetectedProblem(BaseModel):
    """A single architectural pressure detected from the scenario.

    Every problem is backed by evidence — the specific scenario fields
    and profile classifications that triggered it.
    """

    problem_id: str
    name: str
    severity: ProblemSeverity
    description: str
    evidence: dict[str, object]
    source_fields: list[str]
