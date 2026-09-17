"""Conflict Resolver — detects and removes incompatible recommendation pairs.

Three types of filtering:
1. Hard constraint violations — techniques that conflict with scenario requirements
2. Explicit conflicts — technique A declares it conflicts with technique B
3. Prerequisite enforcement — technique A requires B; if B was dropped, drop A too
"""

from __future__ import annotations

from storage_advisor.domain.recommendations import Recommendation
from storage_advisor.domain.scenario import Scenario


def _filter_hard_constraints(
    recommendations: list[Recommendation],
    scenario: Scenario,
) -> list[Recommendation]:
    """Remove techniques that violate hard scenario constraints."""
    filtered: list[Recommendation] = []
    for rec in recommendations:
        if _violates_hard_constraint(rec, scenario):
            continue
        filtered.append(rec)
    return filtered


def _violates_hard_constraint(rec: Recommendation, scenario: Scenario) -> bool:
    """Check if a recommendation violates any hard constraint."""
    # Sharding is only justified at very high scale
    if rec.technique_id == "sharding":
        if scenario.expected_users < 1_000_000 and scenario.current_storage_gb < 1_000:
            return True

    # Deduplication is questionable for very small datasets
    if rec.technique_id == "deduplication":
        if scenario.current_storage_gb < 100:
            return True

    return False


def _resolve_explicit_conflicts(
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    """When two techniques conflict, keep the one with the higher alignment score.

    Recommendations must be sorted by alignment_score descending before calling.
    """
    kept_ids: set[str] = set()
    removed_ids: set[str] = set()
    result: list[Recommendation] = []

    for rec in recommendations:
        if rec.technique_id in removed_ids:
            continue

        conflicts_with_kept = False
        for conflict_id in rec.conflicts_with:
            if conflict_id in kept_ids:
                conflicts_with_kept = True
                break

        if conflicts_with_kept:
            removed_ids.add(rec.technique_id)
            continue

        kept_ids.add(rec.technique_id)
        result.append(rec)

    return result


def _enforce_prerequisites(
    recommendations: list[Recommendation],
) -> list[Recommendation]:
    """If technique A requires prerequisite B and B is not in the list, drop A."""
    kept_ids = {r.technique_id for r in recommendations}
    result: list[Recommendation] = []

    for rec in recommendations:
        missing_prereqs = [p for p in rec.prerequisites if p not in kept_ids]
        if missing_prereqs:
            continue
        result.append(rec)

    return result


def resolve_conflicts(
    recommendations: list[Recommendation],
    scenario: Scenario,
) -> list[Recommendation]:
    """Apply all conflict resolution passes in order.

    1. Remove hard constraint violations
    2. Resolve explicit conflicts (higher score wins)
    3. Enforce prerequisites
    """
    result = _filter_hard_constraints(recommendations, scenario)
    result = _resolve_explicit_conflicts(result)
    result = _enforce_prerequisites(result)
    return result
