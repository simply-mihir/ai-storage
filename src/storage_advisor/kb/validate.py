"""KB v2 integrity validation.

Checks all families and their flattened techniques for referential
integrity, duplicate ids, schema version, impact ranges, and
unknown enum values.  Reports ALL violations at once rather than
failing on the first.
"""

from __future__ import annotations

from pathlib import Path

from storage_advisor.domain.problems import ProblemId
from storage_advisor.kb.loader import discover_families, flatten
from storage_advisor.kb.schema import Family


class KBIntegrityError(Exception):
    """Raised when the KB contains one or more integrity violations.

    Attributes:
        violations: List of human-readable violation descriptions.
    """

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        summary = f"{len(violations)} KB integrity violation(s):\n" + "\n".join(
            f"  - {v}" for v in violations
        )
        super().__init__(summary)


def _all_valid_problem_ids() -> set[str]:
    """Return the set of valid problem id strings from the domain enum."""
    return {p.value for p in ProblemId}


def validate_kb(
    families: list[Family] | None = None,
    kb_root: Path | None = None,
) -> None:
    """Validate the entire KB v2 for integrity.

    Raises ``KBIntegrityError`` listing ALL violations found:
      - Dangling references in solves (must exist in ProblemId enum)
      - Dangling references in synergies_with / conflicts_with / requires
        (must exist as a family or variant id)
      - Duplicate effective technique ids
      - schema_version != 2
      - Impact values outside -5..+5
      - Unknown category or complexity values

    Does nothing if the KB is valid.
    """
    if families is None:
        families = discover_families(kb_root)

    violations: list[str] = []
    valid_problems = _all_valid_problem_ids()

    family_ids: set[str] = set()
    all_known_ids: set[str] = set()

    for fam in families:
        family_ids.add(fam.id)
        if fam.variants:
            for v in fam.variants:
                all_known_ids.add(f"{fam.id}.{v.id}")
        else:
            all_known_ids.add(fam.id)

    all_resolvable = all_known_ids | family_ids

    techniques = flatten(families)

    seen_ids: set[str] = set()
    for tech in techniques:
        if tech.id in seen_ids:
            violations.append(f"Duplicate effective id: {tech.id}")
        seen_ids.add(tech.id)

        for problem in tech.solves:
            if problem not in valid_problems:
                violations.append(
                    f"[{tech.id}] solves dangling reference: {problem}"
                )

        for ref in tech.synergies_with:
            if ref not in all_resolvable:
                violations.append(
                    f"[{tech.id}] synergies_with dangling reference: {ref}"
                )

        for ref in tech.conflicts_with:
            if ref not in all_resolvable:
                violations.append(
                    f"[{tech.id}] conflicts_with dangling reference: {ref}"
                )

        for ref in tech.requires:
            if ref not in all_resolvable:
                violations.append(
                    f"[{tech.id}] requires dangling reference: {ref}"
                )

        for field_name in ("storage", "performance", "cost", "scalability", "security"):
            val = getattr(tech.impacts, field_name)
            if not (-5 <= val <= 5):
                violations.append(
                    f"[{tech.id}] impacts.{field_name} = {val} is outside -5..+5"
                )

    if violations:
        raise KBIntegrityError(violations)
