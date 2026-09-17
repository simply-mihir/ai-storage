"""Recommendation Engine — orchestrates the complete pipeline.

Scenario → Profile → Problems → Candidates → Scored → Filtered → Strategy
"""

from __future__ import annotations

from storage_advisor.detection.problem_detector import detect_problems
from storage_advisor.domain.recommendations import (
    RecommendationResult,
    Recommendation,
    Strategy,
)
from storage_advisor.domain.scenario import Scenario
from storage_advisor.domain.techniques import Technique
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.profiling.workload_profiler import WorkloadProfile, profile_workload
from storage_advisor.recommendation.candidate_generator import generate_candidates
from storage_advisor.recommendation.conflict_resolver import resolve_conflicts
from storage_advisor.recommendation.rule_engine import evaluate_all_candidates


# ---------------------------------------------------------------------------
# Strategy construction — grouping recommendations by workload domain
# ---------------------------------------------------------------------------

_STRATEGY_MAPPING: dict[str, list[str]] = {
    "transactional": [
        "partitioning", "indexing", "sharding", "schema_optimization",
        "query_optimization",
    ],
    "object_storage": [
        "object_storage", "chunking", "lifecycle_management",
    ],
    "caching": [
        "caching",
    ],
    "analytics": [
        "columnar_storage", "data_aggregation", "parquet_format",
        "materialized_views",
    ],
    "archival": [
        "archiving", "tiered_storage", "data_pruning",
    ],
    "security": [
        "replication",
    ],
    "general": [
        "compression", "deduplication",
    ],
}


def _build_strategy(recommendations: list[Recommendation]) -> Strategy:
    """Group recommendations into workload-domain buckets."""
    buckets: dict[str, list[Recommendation]] = {
        key: [] for key in _STRATEGY_MAPPING
    }

    assigned = set()
    for rec in recommendations:
        for bucket_name, technique_ids in _STRATEGY_MAPPING.items():
            if rec.technique_id in technique_ids:
                buckets[bucket_name].append(rec)
                assigned.add(rec.technique_id)

    for rec in recommendations:
        if rec.technique_id not in assigned:
            buckets["general"].append(rec)

    return Strategy(**buckets)


def _build_scenario_summary(scenario: Scenario) -> dict[str, object]:
    """Create a compact scenario summary for the output."""
    return {
        "business_domain": scenario.business_domain,
        "company_size": scenario.company_size,
        "expected_users": scenario.expected_users,
        "concurrent_users": scenario.concurrent_users,
        "current_storage_gb": scenario.current_storage_gb,
        "daily_growth_gb": scenario.daily_growth_gb,
        "data_types": scenario.data_types,
        "read_intensity": scenario.read_intensity,
        "write_intensity": scenario.write_intensity,
        "latency_requirement_ms": scenario.latency_requirement_ms,
        "availability_requirement": scenario.availability_requirement,
        "retention_years": scenario.retention_years,
        "budget_level": scenario.budget_level,
        "analytics_required": scenario.analytics_required,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_recommendation_engine(
    scenario: Scenario,
    techniques: list[Technique] | None = None,
) -> RecommendationResult:
    """Execute the full recommendation pipeline.

    Steps:
    1. Profile the workload
    2. Detect problems
    3. Generate candidates (match problems → techniques)
    4. Score candidates (rule engine)
    5. Filter conflicts and hard constraints
    6. Build coherent strategy
    """
    if techniques is None:
        techniques = load_techniques()

    profile: WorkloadProfile = profile_workload(scenario)
    problems = detect_problems(scenario, profile)
    candidates = generate_candidates(problems, techniques)
    scored = evaluate_all_candidates(candidates, problems, profile, scenario)
    filtered = resolve_conflicts(scored, scenario)
    strategy = _build_strategy(filtered)

    return RecommendationResult(
        scenario_summary=_build_scenario_summary(scenario),
        detected_problems=[p.model_dump() for p in problems],
        recommendations=filtered,
        strategy=strategy,
        assumptions=[
            "All impact estimates are model-based, not measured production values",
            "Compression ratios assume general-purpose lossless compression",
            "Cache hit rates are assumed, not measured",
            "Cost impacts are relative directional estimates, not exact dollar amounts",
            "Technique applicability is based on workload profile classification thresholds",
        ],
    )
