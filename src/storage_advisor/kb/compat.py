"""KB v2 → v1 compatibility layer.

Produces legacy-shaped dicts matching the flat YAML schema so the
existing recommendation engine could consume KB v2 data without
code changes.

NOTE: The v2 ``security`` impact dimension is dropped in this view
because the legacy schema has no security impact field.
"""

from __future__ import annotations

from pathlib import Path

from storage_advisor.kb.loader import flatten
from storage_advisor.kb.schema import EffectiveTechnique, Family

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


def _score_to_legacy(score: int) -> str:
    """Map a signed -5..+5 impact score to a legacy ImpactLevel string."""
    return _IMPACT_SCORE_TO_LEGACY.get(score, "NEUTRAL")


def _technique_to_legacy_dict(tech: EffectiveTechnique) -> dict:
    """Convert one EffectiveTechnique to a legacy-shaped dict.

    The output matches the keys consumed by
    ``storage_advisor.domain.techniques.Technique``:
    id, name, category, solves, applicable_when, conflicts_with,
    benefits, disadvantages, implementation_complexity, and the four
    impact fields (storage, performance, cost, scalability).

    The v2 ``security`` impact is intentionally dropped because the
    legacy schema has no security impact field.
    """
    return {
        "id": tech.id,
        "name": tech.name,
        "category": tech.category.upper(),
        "description": tech.summary,
        "solves": list(tech.solves),
        "applicable_when": {k: list(v) for k, v in tech.applicable_when.items()},
        "conflicts_with": list(tech.conflicts_with),
        "benefits": list(tech.benefits),
        "disadvantages": list(tech.disadvantages),
        "implementation_complexity": tech.implementation_complexity.upper(),
        "storage_impact": _score_to_legacy(tech.impacts.storage),
        "performance_impact": _score_to_legacy(tech.impacts.performance),
        "cost_impact": _score_to_legacy(tech.impacts.cost),
        "scalability_impact": _score_to_legacy(tech.impacts.scalability),
        "prerequisites": list(tech.requires),
        "not_recommended_when": [aw.condition for aw in tech.avoid_when],
    }


def flat_view(
    families: list[Family] | None = None,
    kb_root: Path | None = None,
) -> list[dict]:
    """Return legacy-shaped dicts for all effective techniques in KB v2.

    Each dict has the same keys as a v1 technique entry, suitable for
    constructing ``storage_advisor.domain.techniques.Technique`` instances.

    The v2 ``security`` impact dimension is dropped because the legacy
    schema does not include it.
    """
    techniques = flatten(families=families, kb_root=kb_root)
    return [_technique_to_legacy_dict(t) for t in techniques]
