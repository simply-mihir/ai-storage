"""KB v2 integrity validation.

Checks all families and their flattened techniques for referential
integrity, duplicate ids, self-references, requires cycles, and
impact ranges.  Reports ALL violations at once rather than failing
on the first.  Asymmetric relationships are reported as non-fatal
warnings in the returned ``KBReport``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

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


@dataclass
class KBReport:
    """Result of ``validate_kb`` when the KB has no fatal violations.

    Attributes:
        violations: Always empty when returned (non-empty raises instead).
        warnings: Non-fatal issues such as asymmetric relationships.
    """

    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _all_valid_problem_ids() -> set[str]:
    """Return the set of valid problem id strings from the domain enum."""
    return {p.value for p in ProblemId}


def validate_kb(
    families: list[Family] | None = None,
    kb_root: Path | None = None,
) -> KBReport:
    """Validate the entire KB v2 for integrity.

    Raises ``KBIntegrityError`` listing ALL violations found:
      - Dangling references in solves (must exist in ProblemId enum)
      - Dangling references in synergies_with / conflicts_with / requires
      - Duplicate effective technique ids
      - Impact values outside -5..+5
      - Self-references (any non-solves relationship resolving to
        src == dst after family-reference expansion); family-level
        self-lists likewise
      - REQUIRES cycles (directed cycle among requires edges)

    Returns a ``KBReport`` with non-fatal warnings when the KB is valid:
      - Asymmetric synergies_with or conflicts_with (declared by one
        side only)

    Existing call sites that ignore the return value or check for
    ``KBIntegrityError`` continue to work unchanged.
    """
    if families is None:
        families = discover_families(kb_root)

    violations: list[str] = []
    warnings: list[str] = []
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

    # ── family-level self-reference check ──
    for fam in families:
        for rel in ("synergies_with", "conflicts_with", "requires"):
            if fam.id in getattr(fam, rel):
                violations.append(
                    f"[{fam.id}] family-level self-reference in {rel}"
                )

    techniques = flatten(families)

    seen_ids: set[str] = set()
    for tech in techniques:
        # duplicate id
        if tech.id in seen_ids:
            violations.append(f"Duplicate effective id: {tech.id}")
        seen_ids.add(tech.id)

        # dangling references
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

        # impact range
        for dim in ("storage", "performance", "cost", "scalability", "security"):
            val = getattr(tech.impacts, dim)
            if not (-5 <= val <= 5):
                violations.append(
                    f"[{tech.id}] impacts.{dim} = {val} is outside -5..+5"
                )

        # effective-level self-reference (solves excluded)
        for rel in ("synergies_with", "conflicts_with", "requires"):
            if tech.id in getattr(tech, rel):
                violations.append(
                    f"[{tech.id}] self-reference in {rel}"
                )

    # ── REQUIRES cycle detection ──
    requires_graph = nx.DiGraph()
    for tech in techniques:
        requires_graph.add_node(tech.id)
        for req in tech.requires:
            if req in seen_ids:
                requires_graph.add_edge(tech.id, req)

    for cycle in nx.simple_cycles(requires_graph):
        path = " -> ".join(cycle + [cycle[0]])
        violations.append(f"REQUIRES cycle: {path}")

    # ── asymmetric relationship warnings ──
    synergy_set: set[tuple[str, str]] = set()
    conflict_set: set[tuple[str, str]] = set()

    for tech in techniques:
        for ref in tech.synergies_with:
            synergy_set.add((tech.id, ref))
        for ref in tech.conflicts_with:
            conflict_set.add((tech.id, ref))

    for a, b in sorted(synergy_set):
        if (b, a) not in synergy_set:
            warnings.append(
                f"Asymmetric synergy: {a} declares synergies_with "
                f"{b} but not vice versa"
            )

    for a, b in sorted(conflict_set):
        if (b, a) not in conflict_set:
            warnings.append(
                f"Asymmetric conflict: {a} declares conflicts_with "
                f"{b} but not vice versa"
            )

    if violations:
        raise KBIntegrityError(violations)

    return KBReport(violations=[], warnings=warnings)
