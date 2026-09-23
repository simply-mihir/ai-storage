"""Workload Profiler — converts raw scenario values into categorical classifications.

The profiler is the bridge between user-provided numbers and the Problem Detector.
Every threshold is a named constant so that tuning is explicit and auditable.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from storage_advisor.domain.scenario import DataType, Intensity, Scenario


# ---------------------------------------------------------------------------
# Classification enums
# ---------------------------------------------------------------------------

class GrowthClass(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class PressureLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LatencyClass(StrEnum):
    RELAXED = "RELAXED"
    MODERATE = "MODERATE"
    LOW_LATENCY = "LOW_LATENCY"
    ULTRA_LOW_LATENCY = "ULTRA_LOW_LATENCY"


class RetentionClass(StrEnum):
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    LONG_TERM = "LONG_TERM"


class AvailabilityClass(StrEnum):
    STANDARD = "STANDARD"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
    MISSION_CRITICAL = "MISSION_CRITICAL"


class CompliancePresence(StrEnum):
    NONE = "NONE"
    PRESENT = "PRESENT"


class ConcurrencyClass(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


# ---------------------------------------------------------------------------
# Thresholds — every number here is an engineering assumption, not an
# industry standard.  See docs/assumptions.md for rationale.
# ---------------------------------------------------------------------------

# Storage growth (GB/day)
GROWTH_LOW_UPPER = 10.0          # <= 10 GB/day is modest for most workloads
GROWTH_MEDIUM_UPPER = 100.0      # 10-100 GB/day is moderate growth
GROWTH_MODERATE_UPPER = 500.0    # 100-500 GB/day is notable but manageable
GROWTH_HIGH_UPPER = 2000.0       # 500-2000 GB/day demands horizontal scaling
                                 # >= 2000 GB/day is extreme growth

# Latency (ms)
LATENCY_ULTRA_LOW_UPPER = 20.0    # sub-20ms demands in-memory / edge caching
LATENCY_LOW_UPPER = 100.0         # 20-100ms is typical low-latency requirement
LATENCY_MODERATE_UPPER = 500.0    # 100-500ms is moderate
                                  # > 500ms is relaxed

# Retention (years)
RETENTION_SHORT_UPPER = 1.0       # <= 1 year is short-term
RETENTION_MEDIUM_UPPER = 3.0      # 1-3 years is medium-term
                                  # > 3 years is long-term

# Unstructured data percentage — when does object storage pressure become high?
UNSTRUCTURED_HIGH_PCT = 50.0      # >= 50% unstructured → high object storage pressure
UNSTRUCTURED_MEDIUM_PCT = 20.0    # 20-50% → medium

# Availability (percentage)
AVAIL_MISSION_CRITICAL = 99.99    # >= 99.99% (four nines)
AVAIL_VERY_HIGH = 99.9            # >= 99.9% (three nines)
AVAIL_HIGH = 99.0                 # >= 99% (two nines)
                                  # < 99% is standard

# Scalability — based on expected users
SCALE_HIGH_USERS = 1_000_000           # >= 1M users is high-scale
SCALE_MEDIUM_USERS = 100_000           # 100K-1M is medium
SCALE_HIGH_CONCURRENT = 50_000         # >= 50K concurrent is high
SCALE_HIGH_GROWTH_GB = 100.0           # reuse growth threshold for scale calc

# Analytics — storage size where analytics workload becomes significant
ANALYTICS_HIGH_STORAGE_GB = 5_000.0    # >= 5 TB and analytics required
ANALYTICS_MEDIUM_STORAGE_GB = 500.0    # >= 500 GB and analytics required

# Disaster recovery
DR_STRICT_RTO_MINUTES = 30.0      # RTO < 30 min is strict
DR_STRICT_RPO_MINUTES = 15.0      # RPO < 15 min is strict

# Unstructured data types — used to detect object storage pressure
UNSTRUCTURED_DATA_TYPES = frozenset({
    DataType.IMAGES,
    DataType.VIDEOS,
    DataType.AUDIO,
    DataType.DOCUMENTS,
})


# ---------------------------------------------------------------------------
# WorkloadProfile — the profiler's output
# ---------------------------------------------------------------------------

class WorkloadProfile(BaseModel):
    """Categorical classification of a workload scenario.

    Every field is derived from scenario values using explicit thresholds.
    The Problem Detector consumes this rather than raw scenario numbers.
    """

    storage_growth: GrowthClass
    read_pressure: PressureLevel
    write_pressure: PressureLevel
    latency_class: LatencyClass
    retention_class: RetentionClass
    object_storage_pressure: PressureLevel
    analytics_pressure: PressureLevel
    scalability_pressure: PressureLevel
    availability_class: AvailabilityClass
    compliance_pressure: CompliancePresence
    disaster_recovery_pressure: PressureLevel


# ---------------------------------------------------------------------------
# Profiler functions — one per classification dimension
# ---------------------------------------------------------------------------

def _classify_storage_growth(daily_growth_gb: float) -> GrowthClass:
    if daily_growth_gb <= GROWTH_LOW_UPPER:
        return GrowthClass.LOW
    if daily_growth_gb <= GROWTH_MEDIUM_UPPER:
        return GrowthClass.MEDIUM
    if daily_growth_gb <= GROWTH_MODERATE_UPPER:
        return GrowthClass.MODERATE
    if daily_growth_gb <= GROWTH_HIGH_UPPER:
        return GrowthClass.HIGH
    return GrowthClass.EXTREME


def _classify_read_pressure(
    read_intensity: str, concurrent_users: int
) -> PressureLevel:
    if read_intensity == Intensity.HIGH:
        return PressureLevel.HIGH
    if read_intensity == Intensity.MEDIUM:
        if concurrent_users >= SCALE_HIGH_CONCURRENT:
            return PressureLevel.HIGH
        return PressureLevel.MEDIUM
    # LOW read intensity
    if concurrent_users >= SCALE_HIGH_CONCURRENT:
        return PressureLevel.MEDIUM
    return PressureLevel.LOW


def _classify_write_pressure(
    write_intensity: str, daily_growth_gb: float
) -> PressureLevel:
    if write_intensity == Intensity.HIGH:
        return PressureLevel.HIGH
    if write_intensity == Intensity.MEDIUM:
        if daily_growth_gb > GROWTH_MEDIUM_UPPER:
            return PressureLevel.HIGH
        return PressureLevel.MEDIUM
    # LOW write intensity
    if daily_growth_gb > GROWTH_MEDIUM_UPPER:
        return PressureLevel.MEDIUM
    return PressureLevel.LOW


def _classify_latency(latency_ms: float) -> LatencyClass:
    if latency_ms <= LATENCY_ULTRA_LOW_UPPER:
        return LatencyClass.ULTRA_LOW_LATENCY
    if latency_ms <= LATENCY_LOW_UPPER:
        return LatencyClass.LOW_LATENCY
    if latency_ms <= LATENCY_MODERATE_UPPER:
        return LatencyClass.MODERATE
    return LatencyClass.RELAXED


def _classify_retention(retention_years: float) -> RetentionClass:
    if retention_years <= RETENTION_SHORT_UPPER:
        return RetentionClass.SHORT_TERM
    if retention_years <= RETENTION_MEDIUM_UPPER:
        return RetentionClass.MEDIUM_TERM
    return RetentionClass.LONG_TERM


def _classify_object_storage_pressure(
    unstructured_pct: float, data_types: list[str]
) -> PressureLevel:
    has_unstructured_types = any(
        dt in UNSTRUCTURED_DATA_TYPES for dt in data_types
    )
    if unstructured_pct >= UNSTRUCTURED_HIGH_PCT and has_unstructured_types:
        return PressureLevel.HIGH
    if unstructured_pct >= UNSTRUCTURED_MEDIUM_PCT or has_unstructured_types:
        return PressureLevel.MEDIUM
    return PressureLevel.LOW


def _classify_analytics_pressure(
    analytics_required: bool, current_storage_gb: float
) -> PressureLevel:
    if not analytics_required:
        return PressureLevel.LOW
    if current_storage_gb >= ANALYTICS_HIGH_STORAGE_GB:
        return PressureLevel.HIGH
    if current_storage_gb >= ANALYTICS_MEDIUM_STORAGE_GB:
        return PressureLevel.MEDIUM
    return PressureLevel.LOW


def _classify_scalability_pressure(
    expected_users: int,
    concurrent_users: int,
    daily_growth_gb: float,
) -> PressureLevel:
    signals = 0
    if expected_users >= SCALE_HIGH_USERS:
        signals += 1
    if concurrent_users >= SCALE_HIGH_CONCURRENT:
        signals += 1
    if daily_growth_gb >= SCALE_HIGH_GROWTH_GB:
        signals += 1

    if signals >= 2:
        return PressureLevel.HIGH
    if signals == 1 or expected_users >= SCALE_MEDIUM_USERS:
        return PressureLevel.MEDIUM
    return PressureLevel.LOW


def _classify_availability(availability_pct: float) -> AvailabilityClass:
    if availability_pct >= AVAIL_MISSION_CRITICAL:
        return AvailabilityClass.MISSION_CRITICAL
    if availability_pct >= AVAIL_VERY_HIGH:
        return AvailabilityClass.VERY_HIGH
    if availability_pct >= AVAIL_HIGH:
        return AvailabilityClass.HIGH
    return AvailabilityClass.STANDARD


def _classify_compliance(compliance_requirements: list[str]) -> CompliancePresence:
    meaningful = [c for c in compliance_requirements if c != "NONE"]
    if meaningful:
        return CompliancePresence.PRESENT
    return CompliancePresence.NONE


def _classify_disaster_recovery(
    rto_minutes: float, rpo_minutes: float
) -> PressureLevel:
    strict_count = 0
    if rto_minutes <= DR_STRICT_RTO_MINUTES:
        strict_count += 1
    if rpo_minutes <= DR_STRICT_RPO_MINUTES:
        strict_count += 1

    if strict_count == 2:
        return PressureLevel.HIGH
    if strict_count == 1:
        return PressureLevel.MEDIUM
    return PressureLevel.LOW


# ---------------------------------------------------------------------------
# V2 derivation functions
# ---------------------------------------------------------------------------

def derive_dr_severity(
    rto_hours: float | None, rpo_hours: float | None,
) -> PressureLevel | None:
    """Derive disaster-recovery severity from v2 hour-based inputs.

    Returns None when both inputs are None (caller falls back to legacy).

    Band table:
        rto <= 1 or rpo <= 0.25  -> HIGH
        rto <= 24 or rpo <= 4    -> MEDIUM
        else                     -> LOW
    """
    if rto_hours is None and rpo_hours is None:
        return None
    rto = rto_hours if rto_hours is not None else float("inf")
    rpo = rpo_hours if rpo_hours is not None else float("inf")
    if rto <= 1 or rpo <= 0.25:
        return PressureLevel.HIGH
    if rto <= 24 or rpo <= 4:
        return PressureLevel.MEDIUM
    return PressureLevel.LOW


def derive_concurrency_class(
    concurrent_users: int | None,
) -> ConcurrencyClass | None:
    """Classify concurrent-user count into bands.

    Returns None when input is None.

    Band table:
        < 1,000    -> LOW
        < 25,000   -> MODERATE
        < 250,000  -> HIGH
        >= 250,000 -> EXTREME
    """
    if concurrent_users is None:
        return None
    if concurrent_users < 1_000:
        return ConcurrencyClass.LOW
    if concurrent_users < 25_000:
        return ConcurrencyClass.MODERATE
    if concurrent_users < 250_000:
        return ConcurrencyClass.HIGH
    return ConcurrencyClass.EXTREME


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def profile_workload(scenario: Scenario) -> WorkloadProfile:
    """Derive a WorkloadProfile from a validated Scenario.

    This is the single entry point for the profiling module. It calls each
    classification function and assembles the result.
    """
    return WorkloadProfile(
        storage_growth=_classify_storage_growth(scenario.daily_growth_gb),
        read_pressure=_classify_read_pressure(
            scenario.read_intensity, scenario.concurrent_users
        ),
        write_pressure=_classify_write_pressure(
            scenario.write_intensity, scenario.daily_growth_gb
        ),
        latency_class=_classify_latency(scenario.latency_requirement_ms),
        retention_class=_classify_retention(scenario.retention_years),
        object_storage_pressure=_classify_object_storage_pressure(
            scenario.unstructured_data_pct, scenario.data_types
        ),
        analytics_pressure=_classify_analytics_pressure(
            scenario.analytics_required, scenario.current_storage_gb
        ),
        scalability_pressure=_classify_scalability_pressure(
            scenario.expected_users,
            scenario.concurrent_users,
            scenario.daily_growth_gb,
        ),
        availability_class=_classify_availability(
            scenario.availability_requirement
        ),
        compliance_pressure=_classify_compliance(
            scenario.compliance_requirements
        ),
        disaster_recovery_pressure=(
            derive_dr_severity(scenario.rto_hours, scenario.rpo_hours)
            or _classify_disaster_recovery(scenario.rto_minutes, scenario.rpo_minutes)
        ),
    )
