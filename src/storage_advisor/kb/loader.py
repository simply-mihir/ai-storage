"""KB v2 loader — discovers YAML files, merges families with variants, and builds a graph.

Merge semantics (family + variant):
  - Dicts: deep-merge recursively (variant keys override family keys;
    unset keys kept; nested dicts recurse).
  - Scalars: variant overrides family (``None`` = inherit).
  - Lists: variant REPLACES family at any depth (a variant extending
    a family list must restate the full list).

All merge functions are pure — they never mutate their Family or
Variant inputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None  # type: ignore[assignment]

from storage_advisor.kb.schema import (
    EffectiveTechnique,
    Family,
    Impacts,
    Variant,
)


def _default_kb_root() -> Path:
    """Return the default KB v2 techniques directory."""
    return Path(__file__).resolve().parent / "techniques"


def discover_families(kb_root: Path | None = None) -> list[Family]:
    """Discover and parse all v2 family YAML files under ``kb_root``.

    Layout: ``kb_root/<category>/<family>.yaml``
    Each file must have ``schema_version: 2`` at the top level.

    Families are returned in deterministic order: sorted by category
    directory name, then by YAML filename within each category.
    """
    root = kb_root or _default_kb_root()
    families: list[Family] = []
    for category_dir in sorted(root.iterdir()):
        if not category_dir.is_dir():
            continue
        for yaml_file in sorted(category_dir.glob("*.yaml")):
            raw = yaml.safe_load(yaml_file.read_text())
            if not isinstance(raw, dict):
                continue
            families.append(Family(**raw))
    return families


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge two dicts: override keys win, nested dicts recurse.

    Pure — neither ``base`` nor ``override`` is mutated.
    Lists and scalars at any depth are replaced, not appended.
    """
    merged = dict(base)
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge_dict(merged[key], val)
        else:
            merged[key] = val
    return merged


def _merge_variant(family: Family, variant: Variant) -> EffectiveTechnique:
    """Merge a single variant with its parent family into an EffectiveTechnique.

    Pure — neither ``family`` nor ``variant`` is mutated.

    Merge rules:
      - Scalars: variant value if not None, else family value.
      - Lists: variant list if not None (full replacement), else family list.
      - Dicts (applicable_when, impacts): deep-merge variant over family.
    """
    effective_id = f"{family.id}.{variant.id}"

    solves = variant.solves if variant.solves is not None else list(family.solves)
    synergies = variant.synergies_with if variant.synergies_with is not None else list(family.synergies_with)
    conflicts = variant.conflicts_with if variant.conflicts_with is not None else list(family.conflicts_with)
    requires = variant.requires if variant.requires is not None else list(family.requires)
    avoid = variant.avoid_when if variant.avoid_when is not None else list(family.avoid_when)
    benefits = variant.benefits if variant.benefits is not None else list(family.benefits)
    disadvantages = variant.disadvantages if variant.disadvantages is not None else list(family.disadvantages)
    companies = variant.companies if variant.companies is not None else list(family.companies)
    complexity = (
        variant.implementation_complexity
        if variant.implementation_complexity is not None
        else family.implementation_complexity
    )

    if variant.applicable_when is not None:
        applicable = _deep_merge_dict(
            {k: list(v) for k, v in family.applicable_when.items()},
            variant.applicable_when,
        )
    else:
        applicable = {k: list(v) for k, v in family.applicable_when.items()}

    if variant.impacts is not None:
        base_impacts = family.impacts.model_dump()
        override_impacts = variant.impacts.model_dump(exclude_unset=True)
        merged_impacts = _deep_merge_dict(base_impacts, override_impacts)
        impacts = Impacts(**merged_impacts)
    else:
        impacts = family.impacts.model_copy()

    return EffectiveTechnique(
        id=effective_id,
        name=variant.name,
        category=family.category,
        summary=(
            variant.summary
            if variant.summary is not None
            else family.summary
        ),
        mechanism=(
            variant.mechanism
            if variant.mechanism is not None
            else (family.mechanism or "")
        ),
        solves=solves,
        synergies_with=synergies,
        conflicts_with=conflicts,
        requires=requires,
        avoid_when=avoid,
        applicable_when=applicable,
        implementation_complexity=complexity,
        impacts=impacts,
        benefits=benefits,
        disadvantages=disadvantages,
        companies=companies,
    )


def _family_to_effective(family: Family) -> EffectiveTechnique:
    """Convert a family with no variants into a single EffectiveTechnique.

    Pure — ``family`` is not mutated.
    """
    return EffectiveTechnique(
        id=family.id,
        name=family.name,
        category=family.category,
        summary=family.summary,
        mechanism=family.mechanism or "",
        solves=list(family.solves),
        synergies_with=list(family.synergies_with),
        conflicts_with=list(family.conflicts_with),
        requires=list(family.requires),
        avoid_when=list(family.avoid_when),
        applicable_when={k: list(v) for k, v in family.applicable_when.items()},
        implementation_complexity=family.implementation_complexity,
        impacts=family.impacts.model_copy(),
        benefits=list(family.benefits),
        disadvantages=list(family.disadvantages),
        companies=list(family.companies),
    )


def _expand_family_refs(
    refs: list[str],
    family_to_variants: dict[str, list[str]],
) -> list[str]:
    """Expand family-level references to their variant-level ids.

    If a reference matches a family id that has variants, it is replaced
    by all that family's variant ids. Otherwise it passes through unchanged.
    """
    expanded: list[str] = []
    for ref in refs:
        if family_to_variants.get(ref):
            expanded.extend(family_to_variants[ref])
        else:
            expanded.append(ref)
    return expanded


def flatten(
    families: list[Family] | None = None,
    kb_root: Path | None = None,
) -> list[EffectiveTechnique]:
    """Flatten families into a list of EffectiveTechniques.

    Variant effective id = ``<family_id>.<variant_id>``.
    A family with no variants yields one record with id = family id.

    Relationship fields (synergies_with, conflicts_with, requires) that
    reference a family id are expanded to reference all its variant ids.

    Pure: input Family/Variant objects are never mutated.
    Output order: families by discovery order (sorted file paths),
    variants in declaration order within each family.
    """
    if families is None:
        families = discover_families(kb_root)

    family_to_variants: dict[str, list[str]] = {}
    for fam in families:
        if fam.variants:
            family_to_variants[fam.id] = [
                f"{fam.id}.{v.id}" for v in fam.variants
            ]
        else:
            family_to_variants[fam.id] = []

    techniques: list[EffectiveTechnique] = []
    for fam in families:
        if fam.variants:
            for variant in fam.variants:
                techniques.append(_merge_variant(fam, variant))
        else:
            techniques.append(_family_to_effective(fam))

    return [
        tech.model_copy(update={
            "synergies_with": _expand_family_refs(
                tech.synergies_with, family_to_variants,
            ),
            "conflicts_with": _expand_family_refs(
                tech.conflicts_with, family_to_variants,
            ),
            "requires": _expand_family_refs(
                tech.requires, family_to_variants,
            ),
        })
        for tech in techniques
    ]


def project_graph(
    techniques: list[EffectiveTechnique] | None = None,
    kb_root: Path | None = None,
) -> nx.DiGraph:
    """Build a NetworkX DiGraph from the effective techniques.

    Nodes:
      - Technique ids (kind='technique')
      - Problem ids (kind='problem')

    Edges (one per logical relationship):
      - SOLVES: technique -> problem (directed)
      - REQUIRES: technique -> technique (directed)
      - CONFLICTS: sorted(a, b) canonical direction, undirected=True, deduped
      - SYNERGIZES: sorted(a, b) canonical direction, undirected=True, deduped

    Undirected edges use canonical endpoint order (lexicographically sorted
    id tuple) and are deduplicated: mutual declarations produce one edge.
    """
    if nx is None:  # pragma: no cover
        msg = (
            "networkx is required for project_graph(); "
            "install it with: pip install networkx"
        )
        raise ImportError(msg)

    if techniques is None:
        techniques = flatten(kb_root=kb_root)

    g: nx.DiGraph = nx.DiGraph()
    seen_conflicts: set[tuple[str, str]] = set()
    seen_synergies: set[tuple[str, str]] = set()

    for tech in techniques:
        g.add_node(tech.id, kind="technique")

        for problem_id in tech.solves:
            if not g.has_node(problem_id):
                g.add_node(problem_id, kind="problem")
            g.add_edge(tech.id, problem_id, relation="SOLVES")

        for req in tech.requires:
            if not g.has_node(req):
                g.add_node(req, kind="technique")
            g.add_edge(tech.id, req, relation="REQUIRES")

        for conflict in tech.conflicts_with:
            pair = tuple(sorted((tech.id, conflict)))
            if pair not in seen_conflicts:
                seen_conflicts.add(pair)
                if not g.has_node(conflict):
                    g.add_node(conflict, kind="technique")
                g.add_edge(
                    pair[0], pair[1],
                    relation="CONFLICTS", undirected=True,
                )

        for syn in tech.synergies_with:
            pair = tuple(sorted((tech.id, syn)))
            if pair not in seen_synergies:
                seen_synergies.add(pair)
                if not g.has_node(syn):
                    g.add_node(syn, kind="technique")
                g.add_edge(
                    pair[0], pair[1],
                    relation="SYNERGIZES", undirected=True,
                )

    return g
