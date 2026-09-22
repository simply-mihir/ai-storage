"""KB v2 → v1 compatibility layer.

Produces legacy-shaped dicts matching the flat YAML schema so the
existing recommendation engine can consume KB v2 data without code
changes.

The rollup emits ONE record per family using family-level fields only.
Variants are v2-graph refinements and do not appear in this view.

NOTE: The v2 ``security`` impact dimension is dropped because the
legacy schema has no security impact field.
"""

from __future__ import annotations

from pathlib import Path

from storage_advisor.kb.loader import discover_families
from storage_advisor.kb.schema import Family

_IMPACT_SCORE_TO_LEGACY = {
    5: "HIGH_IMPROVEMENT",
    4: "HIGH_IMPROVEMENT",
    3: "MODERATE_IMPROVEMENT",
    2: "SLIGHT_IMPROVEMENT",
    1: "SLIGHT_IMPROVEMENT",
    0: "NEUTRAL",
    -1: "SLIGHT_INCREASE",
    -2: "MODERATE_INCREASE",
    -3: "MODERATE_INCREASE",
    -4: "MODERATE_INCREASE",
    -5: "MODERATE_INCREASE",
}

V2_TO_LEGACY_CATEGORY: dict[str, str] = {
    "storage": "STORAGE",
    "database": "DATABASE",
    "performance": "PERFORMANCE",
    "analytics": "ANALYTICS",
    "reliability": "STORAGE",
    "architecture": "DATABASE",
    "security": "STORAGE",
}


def _score_to_legacy(score: int) -> str:
    """Map a signed -5..+5 impact score to a legacy ImpactLevel string."""
    return _IMPACT_SCORE_TO_LEGACY.get(score, "NEUTRAL")


def _family_to_legacy_dict(fam: Family) -> dict:
    """Convert one Family to a legacy-shaped dict using family-level fields only.

    The output matches the keys consumed by
    ``storage_advisor.domain.techniques.Technique``.
    """
    cat = fam.legacy_category or V2_TO_LEGACY_CATEGORY.get(
        fam.category, fam.category.upper()
    )
    return {
        "id": fam.id,
        "name": fam.name,
        "category": cat,
        "description": fam.summary,
        "solves": list(fam.solves),
        "applicable_when": {k: list(v) for k, v in fam.applicable_when.items()},
        "conflicts_with": list(fam.conflicts_with) if fam.live_relationships else [],
        "benefits": list(fam.benefits),
        "disadvantages": list(fam.disadvantages),
        "implementation_complexity": fam.implementation_complexity.upper(),
        "storage_impact": _score_to_legacy(fam.impacts.storage),
        "performance_impact": _score_to_legacy(fam.impacts.performance),
        "cost_impact": _score_to_legacy(fam.impacts.cost),
        "scalability_impact": _score_to_legacy(fam.impacts.scalability),
        "prerequisites": list(fam.requires),
        "not_recommended_when": [aw.condition for aw in fam.avoid_when],
        "engine_exposure": fam.engine_exposure,
    }


def flat_view(
    families: list[Family] | None = None,
    kb_root: Path | None = None,
) -> list[dict]:
    """Return legacy-shaped dicts for all families in KB v2.

    Each dict has the same keys as a v1 technique entry (plus
    ``engine_exposure``), suitable for constructing
    ``storage_advisor.domain.techniques.Technique`` instances after
    stripping the extra field.

    Emits ONE record per family using family-level fields only.
    Variants are v2-graph refinements and do not appear in this view.
    """
    if families is None:
        families = discover_families(kb_root=kb_root)
    return [_family_to_legacy_dict(fam) for fam in families]
