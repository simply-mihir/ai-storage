"""Recommendation Engine — orchestrates the complete pipeline.

Scenario → Profile → Problems → Candidates → Scored → Filtered → Strategy
"""

from __future__ import annotations

from storage_advisor.detection.problem_detector import detect_problems
from storage_advisor.domain.problems import DetectedProblem
from storage_advisor.domain.recommendations import (
    AlternativeStrategy,
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
from storage_advisor.recommendation.rule_engine import (
    evaluate_all_candidates,
    _compute_problem_coverage_score,
    _compute_profile_alignment_score,
    _determine_priority,
    _build_evidence,
    _build_rationale,
)


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
# Alternative strategies
# ---------------------------------------------------------------------------

COST_OPT_COVERAGE_WEIGHT = 0.7
COST_OPT_ALIGNMENT_WEIGHT = 0.3
COST_OPT_HIGH_COMPLEXITY_PENALTY = 0.15


def _build_lean_alternative(
    primary: list[Recommendation],
) -> AlternativeStrategy:
    return AlternativeStrategy(
        label="Lean architecture",
        focus="Minimum viable — only required components",
        techniques=[r for r in primary if r.priority == "REQUIRED"],
        trade_off="Lower operational complexity, higher risk at scale",
        estimated_cost_delta="Lower upfront, higher remediation risk later",
    )


def _build_cost_optimized_alternative(
    candidates: list[tuple[Technique, list[str]]],
    all_problems: list[DetectedProblem],
    profile: WorkloadProfile,
    scenario: Scenario,
    primary_count: int,
    primary_required_ids: set[str],
) -> AlternativeStrategy:
    scored: list[Recommendation] = []
    for tech, matched in candidates:
        problem_score = _compute_problem_coverage_score(matched, all_problems)
        profile_score = _compute_profile_alignment_score(tech, profile)

        alignment = (
            COST_OPT_COVERAGE_WEIGHT * problem_score
            + COST_OPT_ALIGNMENT_WEIGHT * profile_score
        )
        if tech.implementation_complexity == "HIGH":
            alignment -= COST_OPT_HIGH_COMPLEXITY_PENALTY
        alignment = round(max(alignment, 0.0), 3)

        priority = _determine_priority(alignment, matched, all_problems)
        evidence = _build_evidence(tech, matched, profile)
        rationale = _build_rationale(tech, matched, priority)

        scored.append(Recommendation(
            technique_id=tech.id,
            technique_name=tech.name,
            category=tech.category,
            priority=priority,
            alignment_score=alignment,
            problems_solved=matched,
            rationale=rationale,
            evidence=evidence,
            benefits=tech.benefits,
            disadvantages=tech.disadvantages,
            implementation_complexity=tech.implementation_complexity,
            prerequisites=tech.prerequisites,
            conflicts_with=tech.conflicts_with,
            conditions=tech.not_recommended_when,
        ))

    scored.sort(key=lambda r: r.alignment_score, reverse=True)
    filtered = resolve_conflicts(scored, scenario)

    # Exclude HIGH-complexity techniques unless they are REQUIRED in primary
    filtered = [
        r for r in filtered
        if r.implementation_complexity != "HIGH"
        or r.technique_id in primary_required_ids
    ]

    n = max(primary_count - 2, 0)
    trimmed = filtered[:n]

    return AlternativeStrategy(
        label="Cost-optimized",
        focus="Reduced complexity, lower operational spend",
        techniques=trimmed,
        trade_off="May underperform at extreme scale; lower complexity budget",
        estimated_cost_delta="Estimated 15–25% lower monthly operational cost",
    )


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

    primary_required_ids = {
        r.technique_id for r in filtered if r.priority == "REQUIRED"
    }
    alternatives = [
        _build_lean_alternative(filtered),
        _build_cost_optimized_alternative(
            candidates, problems, profile, scenario, len(filtered),
            primary_required_ids,
        ),
    ]

    return RecommendationResult(
        scenario_summary=_build_scenario_summary(scenario),
        detected_problems=[p.model_dump() for p in problems],
        recommendations=filtered,
        strategy=strategy,
        alternatives=alternatives,
        assumptions=[
            "All impact estimates are model-based, not measured production values",
            "Compression ratios assume general-purpose lossless compression",
            "Cache hit rates are assumed, not measured",
            "Cost impacts are relative directional estimates, not exact dollar amounts",
            "Technique applicability is based on workload profile classification thresholds",
        ],
    )
