"""Problem Detector — maps workload profile + scenario to named architectural problems.

Each detection function checks one problem. A problem fires only when the
profile or scenario crosses an explicit threshold. Every detected problem
carries the evidence that triggered it so the recommendation can explain itself.
"""

from __future__ import annotations

from storage_advisor.domain.problems import DetectedProblem, ProblemId, ProblemSeverity
from storage_advisor.domain.scenario import DataType, Scenario
from storage_advisor.profiling.workload_profiler import (
    AvailabilityClass,
    CompliancePresence,
    GrowthClass,
    LatencyClass,
    PressureLevel,
    RetentionClass,
    WorkloadProfile,
)

# Threshold for "large transactional dataset" detection (GB)
LARGE_TRANSACTIONAL_STORAGE_GB = 1_000.0


# ---------------------------------------------------------------------------
# Individual detectors — each returns a DetectedProblem or None
# ---------------------------------------------------------------------------

_GROWTH_PROBLEM_MAP: dict[str, tuple[str, str, str, str]] = {
    GrowthClass.MODERATE: (
        ProblemId.MODERATE_STORAGE_GROWTH,
        "Moderate Storage Growth",
        ProblemSeverity.MEDIUM,
        "The workload generates notable daily data that will accumulate over "
        "time, requiring lifecycle management and cost monitoring.",
    ),
    GrowthClass.HIGH: (
        ProblemId.HIGH_STORAGE_GROWTH,
        "High Storage Growth",
        ProblemSeverity.HIGH,
        "The workload generates large volumes of new data daily, demanding "
        "horizontal scaling, lifecycle management, and tiered storage.",
    ),
    GrowthClass.EXTREME: (
        ProblemId.EXTREME_STORAGE_GROWTH,
        "Extreme Storage Growth",
        ProblemSeverity.CRITICAL,
        "The workload generates massive data volumes daily, requiring "
        "aggressive sharding, tiered storage, and automated lifecycle policies.",
    ),
}


def _detect_storage_growth(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    entry = _GROWTH_PROBLEM_MAP.get(profile.storage_growth)
    if entry is None:
        return None
    problem_id, name, severity, description = entry
    return DetectedProblem(
        problem_id=problem_id,
        name=name,
        severity=severity,
        description=description,
        evidence={
            "daily_growth_gb": scenario.daily_growth_gb,
            "storage_growth_class": profile.storage_growth,
        },
        source_fields=["daily_growth_gb"],
    )


def _detect_high_read_latency(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    high_read = profile.read_pressure == PressureLevel.HIGH
    low_latency = profile.latency_class in (
        LatencyClass.LOW_LATENCY,
        LatencyClass.ULTRA_LOW_LATENCY,
    )
    if not (high_read and low_latency):
        return None
    return DetectedProblem(
        problem_id=ProblemId.HIGH_READ_LATENCY,
        name="High Read Latency Pressure",
        severity=ProblemSeverity.HIGH,
        description=(
            "High read volume combined with strict latency requirements "
            "creates pressure for caching, indexing, and read optimization."
        ),
        evidence={
            "read_intensity": scenario.read_intensity,
            "latency_requirement_ms": scenario.latency_requirement_ms,
            "concurrent_users": scenario.concurrent_users,
        },
        source_fields=["read_intensity", "latency_requirement_ms", "concurrent_users"],
    )


def _detect_high_write_pressure(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    if profile.write_pressure != PressureLevel.HIGH:
        return None
    return DetectedProblem(
        problem_id=ProblemId.HIGH_WRITE_PRESSURE,
        name="High Write Pressure",
        severity=ProblemSeverity.MEDIUM,
        description=(
            "Heavy write load can create bottlenecks in storage ingestion, "
            "indexing overhead, and replication lag."
        ),
        evidence={
            "write_intensity": scenario.write_intensity,
            "daily_growth_gb": scenario.daily_growth_gb,
        },
        source_fields=["write_intensity", "daily_growth_gb"],
    )


def _detect_large_unstructured_workload(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    if profile.object_storage_pressure != PressureLevel.HIGH:
        return None
    return DetectedProblem(
        problem_id=ProblemId.LARGE_UNSTRUCTURED_OBJECT_WORKLOAD,
        name="Large Unstructured Object Workload",
        severity=ProblemSeverity.HIGH,
        description=(
            "A dominant share of unstructured data (images, videos, documents) "
            "requires dedicated object storage rather than a relational database."
        ),
        evidence={
            "unstructured_data_pct": scenario.unstructured_data_pct,
            "data_types": scenario.data_types,
        },
        source_fields=["unstructured_data_pct", "data_types"],
    )


def _detect_high_analytics_workload(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    if profile.analytics_pressure not in (PressureLevel.HIGH, PressureLevel.MEDIUM):
        return None
    severity = (
        ProblemSeverity.HIGH
        if profile.analytics_pressure == PressureLevel.HIGH
        else ProblemSeverity.MEDIUM
    )
    return DetectedProblem(
        problem_id=ProblemId.HIGH_ANALYTICS_WORKLOAD,
        name="High Analytics Workload",
        severity=severity,
        description=(
            "Analytics over a large dataset benefits from columnar storage, "
            "aggregation, and separated analytical compute paths."
        ),
        evidence={
            "analytics_required": scenario.analytics_required,
            "current_storage_gb": scenario.current_storage_gb,
        },
        source_fields=["analytics_required", "current_storage_gb"],
    )


def _detect_long_term_retention(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    if profile.retention_class != RetentionClass.LONG_TERM:
        return None
    return DetectedProblem(
        problem_id=ProblemId.LONG_TERM_RETENTION,
        name="Long-Term Retention",
        severity=ProblemSeverity.MEDIUM,
        description=(
            "Multi-year retention creates growing storage costs and requires "
            "lifecycle policies to move aging data to cheaper tiers."
        ),
        evidence={
            "retention_years": scenario.retention_years,
        },
        source_fields=["retention_years"],
    )


def _detect_hot_cold_data_mix(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    has_retention = scenario.retention_years > 1
    has_growth = scenario.daily_growth_gb > 0
    if not (has_retention and has_growth):
        return None
    return DetectedProblem(
        problem_id=ProblemId.HOT_COLD_DATA_MIX,
        name="Hot/Cold Data Mix",
        severity=ProblemSeverity.MEDIUM,
        description=(
            "Ongoing data growth combined with retention means the dataset "
            "contains both frequently accessed (hot) and rarely accessed (cold) data. "
            "A single storage tier wastes cost on cold data."
        ),
        evidence={
            "retention_years": scenario.retention_years,
            "daily_growth_gb": scenario.daily_growth_gb,
        },
        source_fields=["retention_years", "daily_growth_gb"],
    )


def _detect_large_transactional_dataset(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    has_transactions = DataType.TRANSACTIONS in scenario.data_types
    large_storage = scenario.current_storage_gb >= LARGE_TRANSACTIONAL_STORAGE_GB
    if not (has_transactions and large_storage):
        return None
    return DetectedProblem(
        problem_id=ProblemId.LARGE_TRANSACTIONAL_DATASET,
        name="Large Transactional Dataset",
        severity=ProblemSeverity.MEDIUM,
        description=(
            "A large volume of transactional data benefits from partitioning, "
            "indexing optimization, and potentially sharding."
        ),
        evidence={
            "current_storage_gb": scenario.current_storage_gb,
            "data_types": scenario.data_types,
            "structured_data_pct": scenario.structured_data_pct,
        },
        source_fields=["current_storage_gb", "data_types", "structured_data_pct"],
    )


def _detect_high_availability(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    if profile.availability_class not in (
        AvailabilityClass.VERY_HIGH,
        AvailabilityClass.MISSION_CRITICAL,
    ):
        return None
    severity = (
        ProblemSeverity.CRITICAL
        if profile.availability_class == AvailabilityClass.MISSION_CRITICAL
        else ProblemSeverity.HIGH
    )
    return DetectedProblem(
        problem_id=ProblemId.HIGH_AVAILABILITY_REQUIREMENT,
        name="High Availability Requirement",
        severity=severity,
        description=(
            "Strict uptime requirements demand redundancy, replication, "
            "automatic failover, and multi-zone deployment."
        ),
        evidence={
            "availability_requirement": scenario.availability_requirement,
        },
        source_fields=["availability_requirement"],
    )


def _detect_disaster_recovery(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    if profile.disaster_recovery_pressure == PressureLevel.LOW:
        return None
    severity = (
        ProblemSeverity.HIGH
        if profile.disaster_recovery_pressure == PressureLevel.HIGH
        else ProblemSeverity.MEDIUM
    )
    return DetectedProblem(
        problem_id=ProblemId.DISASTER_RECOVERY_REQUIREMENT,
        name="Disaster Recovery Requirement",
        severity=severity,
        description=(
            "Tight RTO/RPO targets require automated backups, replication, "
            "and a tested recovery strategy."
        ),
        evidence={
            "rto_minutes": scenario.rto_minutes,
            "rpo_minutes": scenario.rpo_minutes,
        },
        source_fields=["rto_minutes", "rpo_minutes"],
    )


def _detect_compliance(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    if profile.compliance_pressure != CompliancePresence.PRESENT:
        return None
    frameworks = [c for c in scenario.compliance_requirements if c != "NONE"]
    return DetectedProblem(
        problem_id=ProblemId.COMPLIANCE_REQUIREMENT,
        name="Compliance Requirement",
        severity=ProblemSeverity.HIGH,
        description=(
            "Regulatory compliance constrains storage choices: encryption, "
            "audit logging, data residency, and retention policies may be mandatory."
        ),
        evidence={
            "compliance_requirements": frameworks,
            "sensitive_data": scenario.sensitive_data,
        },
        source_fields=["compliance_requirements", "sensitive_data"],
    )


def _detect_scalability_pressure(
    profile: WorkloadProfile, scenario: Scenario
) -> DetectedProblem | None:
    if profile.scalability_pressure != PressureLevel.HIGH:
        return None
    return DetectedProblem(
        problem_id=ProblemId.SCALABILITY_PRESSURE,
        name="Scalability Pressure",
        severity=ProblemSeverity.HIGH,
        description=(
            "High user count, concurrent load, and data growth combine to "
            "require horizontally scalable storage and compute."
        ),
        evidence={
            "expected_users": scenario.expected_users,
            "concurrent_users": scenario.concurrent_users,
            "daily_growth_gb": scenario.daily_growth_gb,
        },
        source_fields=["expected_users", "concurrent_users", "daily_growth_gb"],
    )


# ---------------------------------------------------------------------------
# Lesson 3 detectors — each emits only when severity >= MEDIUM
# ---------------------------------------------------------------------------

_SENSITIVE_DATA_TYPES = frozenset({
    DataType.TRANSACTIONS,
    DataType.DOCUMENTS,
    DataType.EMBEDDINGS,
})


def _detect_security_exposure(
    profile: WorkloadProfile, scenario: Scenario,
) -> DetectedProblem | None:
    """Detect data-security exposure from sensitive data types."""
    sensitive = [dt for dt in scenario.data_types if dt in _SENSITIVE_DATA_TYPES]
    n = len(sensitive)
    if n == 0:
        return None

    if profile.compliance_pressure == CompliancePresence.PRESENT or n >= 3:
        severity = ProblemSeverity.HIGH
    elif n >= 2 or (n == 1 and profile.retention_class == RetentionClass.LONG_TERM):
        severity = ProblemSeverity.MEDIUM
    else:
        return None

    return DetectedProblem(
        problem_id=ProblemId.SECURITY_EXPOSURE,
        name="Security Exposure",
        severity=severity,
        description=(
            "Sensitive data types combined with compliance or retention "
            "requirements create security exposure requiring encryption, "
            "access controls, and audit logging."
        ),
        evidence={
            "sensitive_data_types": sensitive,
            "compliance_pressure": str(profile.compliance_pressure),
            "retention_class": str(profile.retention_class),
        },
        source_fields=["data_types", "compliance_requirements", "retention_years"],
    )


def _detect_cost_overrun_risk(
    profile: WorkloadProfile, scenario: Scenario,
) -> DetectedProblem | None:
    """Detect cost-overrun risk from growth vs. budget mismatch."""
    constrained = scenario.budget_level in ("LOW", "MEDIUM")
    growth = profile.storage_growth

    if growth == GrowthClass.EXTREME and constrained:
        severity = ProblemSeverity.HIGH
    elif (growth == GrowthClass.HIGH and constrained) or (
        growth == GrowthClass.EXTREME and not constrained
    ):
        severity = ProblemSeverity.MEDIUM
    else:
        return None

    return DetectedProblem(
        problem_id=ProblemId.COST_OVERRUN_RISK,
        name="Cost Overrun Risk",
        severity=severity,
        description=(
            "Rapid storage growth against a constrained budget creates "
            "risk of cost overruns without lifecycle management and "
            "tiered storage strategies."
        ),
        evidence={
            "storage_growth": str(growth),
            "budget_level": scenario.budget_level,
        },
        source_fields=["daily_growth_gb", "budget_level"],
    )


def _detect_query_performance_degradation(
    profile: WorkloadProfile, scenario: Scenario,
) -> DetectedProblem | None:
    """Detect query-performance degradation from read pressure and latency."""
    if profile.read_pressure != PressureLevel.HIGH:
        return None
    if profile.latency_class not in (
        LatencyClass.LOW_LATENCY,
        LatencyClass.ULTRA_LOW_LATENCY,
    ):
        return None

    has_transactions = DataType.TRANSACTIONS in scenario.data_types
    if has_transactions:
        severity = ProblemSeverity.HIGH
    else:
        severity = ProblemSeverity.MEDIUM

    return DetectedProblem(
        problem_id=ProblemId.QUERY_PERFORMANCE_DEGRADATION,
        name="Query Performance Degradation",
        severity=severity,
        description=(
            "High read pressure combined with strict latency requirements "
            "risks query-performance degradation as data grows, requiring "
            "indexing, partitioning, and caching strategies."
        ),
        evidence={
            "read_pressure": str(profile.read_pressure),
            "latency_class": str(profile.latency_class),
            "has_transactions": has_transactions,
        },
        source_fields=["read_intensity", "latency_requirement_ms", "data_types"],
    )


def _detect_maintenance_burden(
    profile: WorkloadProfile, scenario: Scenario,
) -> DetectedProblem | None:
    """Detect maintenance burden from combined infrastructure stress."""
    signals = 0
    if profile.latency_class == LatencyClass.ULTRA_LOW_LATENCY:
        signals += 1
    if profile.write_pressure == PressureLevel.HIGH:
        signals += 1
    if profile.storage_growth in (GrowthClass.HIGH, GrowthClass.EXTREME):
        signals += 1

    if signals == 3:
        severity = ProblemSeverity.HIGH
    elif signals == 2:
        severity = ProblemSeverity.MEDIUM
    else:
        return None

    return DetectedProblem(
        problem_id=ProblemId.MAINTENANCE_BURDEN,
        name="Maintenance Burden",
        severity=severity,
        description=(
            "Ultra-low latency, high write pressure, and rapid growth "
            "combine to create a heavy operational maintenance burden "
            "requiring lifecycle automation and tiered storage."
        ),
        evidence={
            "latency_class": str(profile.latency_class),
            "write_pressure": str(profile.write_pressure),
            "storage_growth": str(profile.storage_growth),
        },
        source_fields=["latency_requirement_ms", "write_intensity", "daily_growth_gb"],
    )


# ---------------------------------------------------------------------------
# All detectors in evaluation order
# ---------------------------------------------------------------------------

_DETECTORS = [
    _detect_storage_growth,
    _detect_high_read_latency,
    _detect_high_write_pressure,
    _detect_large_unstructured_workload,
    _detect_high_analytics_workload,
    _detect_long_term_retention,
    _detect_hot_cold_data_mix,
    _detect_large_transactional_dataset,
    _detect_high_availability,
    _detect_disaster_recovery,
    _detect_compliance,
    _detect_scalability_pressure,
    _detect_security_exposure,
    _detect_cost_overrun_risk,
    _detect_query_performance_degradation,
    _detect_maintenance_burden,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_problems(
    scenario: Scenario, profile: WorkloadProfile
) -> list[DetectedProblem]:
    """Run all problem detectors and return those that fired.

    Problems are returned in detection order, highest severity first
    within each severity level.
    """
    problems: list[DetectedProblem] = []
    for detector in _DETECTORS:
        result = detector(profile, scenario)
        if result is not None:
            problems.append(result)

    severity_order = {
        ProblemSeverity.CRITICAL: 0,
        ProblemSeverity.HIGH: 1,
        ProblemSeverity.MEDIUM: 2,
        ProblemSeverity.LOW: 3,
    }
    problems.sort(key=lambda p: severity_order[p.severity])
    return problems
