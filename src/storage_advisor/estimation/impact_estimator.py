"""Impact Estimator — transparent, assumption-driven estimates for storage/cost/latency.

Every estimate is labeled MODEL-BASED and carries explicit assumptions.
These are NOT measured production values — they are directional indicators
to help users understand the relative impact of recommendations.
"""

from __future__ import annotations

from pydantic import BaseModel

from storage_advisor.domain.recommendations import Recommendation
from storage_advisor.domain.scenario import Scenario
from storage_advisor.integrations.pricing import AWSPricingClient, RealCostEstimate


# ---------------------------------------------------------------------------
# Estimation assumptions — each is a named constant with rationale
# ---------------------------------------------------------------------------

# Compression: typical lossless ratio for mixed data
ASSUMED_COMPRESSION_RATIO = 0.45  # 45% of original → 55% savings

# Deduplication: assumed redundancy rate in enterprise data
ASSUMED_DEDUP_RATIO = 0.20  # 20% of data is duplicate

# Tiered storage: cost ratio between hot and cold tiers
ASSUMED_HOT_TIER_COST_PER_GB = 0.023  # $/GB/month (S3 Standard)
ASSUMED_COLD_TIER_COST_PER_GB = 0.004  # $/GB/month (S3 Glacier)
ASSUMED_COLD_DATA_FRACTION = 0.60  # 60% of retained data becomes cold over time

# Caching: assumed cache hit rate and latency improvement
ASSUMED_CACHE_HIT_RATE = 0.80  # 80% of reads served from cache
ASSUMED_CACHE_LATENCY_MS = 2.0  # cache response time
ASSUMED_DB_LATENCY_MS = 50.0  # typical database response time

# Partitioning: query speedup factor for partition-aligned queries
ASSUMED_PARTITION_SPEEDUP = 0.40  # queries run at 40% of original time

# Indexing: lookup speedup
ASSUMED_INDEX_SPEEDUP = 0.10  # indexed lookups at 10% of scan time

# Columnar storage: compression advantage over row format
ASSUMED_COLUMNAR_COMPRESSION = 0.30  # 30% of row-oriented size

# Archiving: fraction of data eligible after retention period
ASSUMED_ARCHIVE_ELIGIBLE_FRACTION = 0.40  # 40% of data can move to archive


# ---------------------------------------------------------------------------
# Estimate models
# ---------------------------------------------------------------------------

class StorageEstimate(BaseModel):
    """Estimated storage impact."""
    current_storage_gb: float
    projected_storage_gb: float
    estimated_reduction_gb: float
    estimated_reduction_pct: float
    assumptions: list[str]
    label: str = "MODEL-BASED ESTIMATE"


class CostEstimate(BaseModel):
    """Estimated monthly cost impact."""
    estimated_monthly_baseline_usd: float
    estimated_monthly_optimized_usd: float
    estimated_monthly_savings_usd: float
    estimated_savings_pct: float
    assumptions: list[str]
    label: str = "MODEL-BASED ESTIMATE"


class LatencyEstimate(BaseModel):
    """Estimated latency impact."""
    current_effective_latency_ms: float
    estimated_optimized_latency_ms: float
    estimated_improvement_pct: float
    assumptions: list[str]
    label: str = "MODEL-BASED ESTIMATE"


class ImpactReport(BaseModel):
    """Complete impact estimation report."""
    storage: StorageEstimate
    cost: CostEstimate
    latency: LatencyEstimate
    disclaimer: str = (
        "All estimates are model-based projections using documented assumptions. "
        "Actual results depend on workload characteristics, data distribution, "
        "access patterns, and implementation details."
    )


# ---------------------------------------------------------------------------
# Estimation logic
# ---------------------------------------------------------------------------

def _estimate_storage_impact(
    scenario: Scenario,
    recommendations: list[Recommendation],
) -> StorageEstimate:
    """Estimate cumulative storage reduction from recommended techniques."""
    current = scenario.current_storage_gb
    reduction_factor = 1.0
    assumptions: list[str] = []

    rec_ids = {r.technique_id for r in recommendations}

    if "compression" in rec_ids:
        reduction_factor *= ASSUMED_COMPRESSION_RATIO
        assumptions.append(
            f"Compression ratio: {ASSUMED_COMPRESSION_RATIO:.0%} of original size"
        )

    if "deduplication" in rec_ids:
        reduction_factor *= (1.0 - ASSUMED_DEDUP_RATIO)
        assumptions.append(
            f"Deduplication: {ASSUMED_DEDUP_RATIO:.0%} redundancy eliminated"
        )

    if "columnar_storage" in rec_ids or "parquet_format" in rec_ids:
        analytics_fraction = scenario.structured_data_pct / 100.0
        columnar_savings = analytics_fraction * (1.0 - ASSUMED_COLUMNAR_COMPRESSION)
        reduction_factor *= (1.0 - columnar_savings)
        assumptions.append(
            f"Columnar compression: {ASSUMED_COLUMNAR_COMPRESSION:.0%} of row size "
            f"for {analytics_fraction:.0%} of data"
        )

    if "data_pruning" in rec_ids:
        reduction_factor *= (1.0 - ASSUMED_ARCHIVE_ELIGIBLE_FRACTION * 0.3)
        assumptions.append(
            f"Data pruning: removes ~{ASSUMED_ARCHIVE_ELIGIBLE_FRACTION * 30:.0f}% of pruneable data"
        )

    projected = current * reduction_factor
    reduction = current - projected

    return StorageEstimate(
        current_storage_gb=round(current, 1),
        projected_storage_gb=round(projected, 1),
        estimated_reduction_gb=round(reduction, 1),
        estimated_reduction_pct=round((1.0 - reduction_factor) * 100, 1),
        assumptions=assumptions,
    )


def _estimate_cost_impact(
    scenario: Scenario,
    recommendations: list[Recommendation],
    storage_estimate: StorageEstimate,
) -> CostEstimate:
    """Estimate monthly cost impact using storage tier pricing."""
    assumptions: list[str] = []

    baseline_monthly = scenario.current_storage_gb * ASSUMED_HOT_TIER_COST_PER_GB
    assumptions.append(
        f"Baseline: all data at hot tier (${ASSUMED_HOT_TIER_COST_PER_GB}/GB/month)"
    )

    rec_ids = {r.technique_id for r in recommendations}
    optimized_storage = storage_estimate.projected_storage_gb

    if "tiered_storage" in rec_ids or "archiving" in rec_ids:
        hot_gb = optimized_storage * (1.0 - ASSUMED_COLD_DATA_FRACTION)
        cold_gb = optimized_storage * ASSUMED_COLD_DATA_FRACTION
        optimized_monthly = (
            hot_gb * ASSUMED_HOT_TIER_COST_PER_GB
            + cold_gb * ASSUMED_COLD_TIER_COST_PER_GB
        )
        assumptions.append(
            f"Tiered: {ASSUMED_COLD_DATA_FRACTION:.0%} of data at cold tier "
            f"(${ASSUMED_COLD_TIER_COST_PER_GB}/GB/month)"
        )
    else:
        optimized_monthly = optimized_storage * ASSUMED_HOT_TIER_COST_PER_GB

    savings = baseline_monthly - optimized_monthly
    savings_pct = (savings / baseline_monthly * 100) if baseline_monthly > 0 else 0

    return CostEstimate(
        estimated_monthly_baseline_usd=round(baseline_monthly, 2),
        estimated_monthly_optimized_usd=round(optimized_monthly, 2),
        estimated_monthly_savings_usd=round(savings, 2),
        estimated_savings_pct=round(savings_pct, 1),
        assumptions=assumptions,
    )


def _estimate_latency_impact(
    scenario: Scenario,
    recommendations: list[Recommendation],
) -> LatencyEstimate:
    """Estimate latency improvement from performance techniques."""
    current_latency = scenario.latency_requirement_ms
    improvement_factor = 1.0
    assumptions: list[str] = []

    rec_ids = {r.technique_id for r in recommendations}

    if "caching" in rec_ids:
        effective = (
            ASSUMED_CACHE_HIT_RATE * ASSUMED_CACHE_LATENCY_MS
            + (1 - ASSUMED_CACHE_HIT_RATE) * current_latency
        )
        improvement_factor = effective / current_latency
        assumptions.append(
            f"Cache hit rate: {ASSUMED_CACHE_HIT_RATE:.0%}, "
            f"cache latency: {ASSUMED_CACHE_LATENCY_MS}ms"
        )
    else:
        if "indexing" in rec_ids:
            improvement_factor *= ASSUMED_INDEX_SPEEDUP
            assumptions.append(
                f"Indexing speedup: queries at {ASSUMED_INDEX_SPEEDUP:.0%} of scan time"
            )
        if "partitioning" in rec_ids:
            improvement_factor *= ASSUMED_PARTITION_SPEEDUP
            assumptions.append(
                f"Partitioning speedup: {ASSUMED_PARTITION_SPEEDUP:.0%} of original"
            )

    estimated_latency = current_latency * improvement_factor
    improvement_pct = (1.0 - improvement_factor) * 100

    if not assumptions:
        assumptions.append("No performance techniques applied; no latency change estimated")

    return LatencyEstimate(
        current_effective_latency_ms=round(current_latency, 1),
        estimated_optimized_latency_ms=round(estimated_latency, 1),
        estimated_improvement_pct=round(improvement_pct, 1),
        assumptions=assumptions,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_pricing_client = AWSPricingClient()


def real_cost_estimate(scenario: Scenario, architecture) -> RealCostEstimate:
    return _pricing_client.calculate_monthly_architecture_cost(architecture, scenario)


def estimate_impact(
    scenario: Scenario,
    recommendations: list[Recommendation],
) -> ImpactReport:
    """Produce a complete impact report for the given recommendations.

    All estimates are model-based and carry explicit assumptions.
    """
    storage = _estimate_storage_impact(scenario, recommendations)
    cost = _estimate_cost_impact(scenario, recommendations, storage)
    latency = _estimate_latency_impact(scenario, recommendations)

    return ImpactReport(
        storage=storage,
        cost=cost,
        latency=latency,
    )
