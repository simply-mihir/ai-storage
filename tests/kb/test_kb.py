"""Tests for KB v2: schema, loader, validate, and compat modules."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from storage_advisor.kb.schema import (
    AvoidWhen,
    Company,
    Complexity,
    EffectiveTechnique,
    Family,
    FamilyCategory,
    Impacts,
    Variant,
)
from storage_advisor.kb.loader import (
    _deep_merge_dict,
    _expand_family_refs,
    _family_to_effective,
    _merge_variant,
    discover_families,
    flatten,
    project_graph,
)
from storage_advisor.kb.validate import KBIntegrityError, validate_kb
from storage_advisor.kb.compat import _score_to_legacy, _technique_to_legacy_dict, flat_view


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_family(**overrides) -> Family:
    defaults = dict(
        schema_version=2,
        id="test_fam",
        name="Test Family",
        category="storage",
        summary="A test family",
        mechanism="Does things",
    )
    defaults.update(overrides)
    return Family(**defaults)


def _minimal_variant(**overrides) -> Variant:
    defaults = dict(id="var1", name="Variant 1")
    defaults.update(overrides)
    return Variant(**defaults)


# ---------------------------------------------------------------------------
# 1. Dict deep-merge
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_flat_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 99, "c": 3}
        result = _deep_merge_dict(base, override)
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}, "y": 10}
        override = {"x": {"b": 99, "c": 3}}
        result = _deep_merge_dict(base, override)
        assert result == {"x": {"a": 1, "b": 99, "c": 3}, "y": 10}

    def test_base_unchanged(self):
        base = {"a": {"nested": 1}}
        override = {"a": {"nested": 2}}
        _deep_merge_dict(base, override)
        assert base == {"a": {"nested": 1}}


# ---------------------------------------------------------------------------
# 2. List-replace semantics
# ---------------------------------------------------------------------------

class TestListReplace:
    def test_variant_list_replaces_family(self):
        family = _minimal_family(
            benefits=["family benefit 1", "family benefit 2"],
        )
        variant = _minimal_variant(benefits=["only variant benefit"])
        tech = _merge_variant(family, variant)
        assert tech.benefits == ["only variant benefit"]

    def test_variant_none_inherits_family_list(self):
        family = _minimal_family(
            benefits=["family benefit 1"],
        )
        variant = _minimal_variant()  # benefits=None → inherit
        tech = _merge_variant(family, variant)
        assert tech.benefits == ["family benefit 1"]


# ---------------------------------------------------------------------------
# 3. Scalar override
# ---------------------------------------------------------------------------

class TestScalarOverride:
    def test_variant_overrides_complexity(self):
        family = _minimal_family(implementation_complexity="low")
        variant = _minimal_variant(implementation_complexity="high")
        tech = _merge_variant(family, variant)
        assert tech.implementation_complexity == Complexity.HIGH

    def test_variant_inherits_complexity_when_none(self):
        family = _minimal_family(implementation_complexity="low")
        variant = _minimal_variant()
        tech = _merge_variant(family, variant)
        assert tech.implementation_complexity == Complexity.LOW


# ---------------------------------------------------------------------------
# 4. Variant inheriting family solves when unspecified
# ---------------------------------------------------------------------------

class TestVariantInheritsSolves:
    def test_inherits_solves(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH", "HIGH_STORAGE_GROWTH"],
        )
        variant = _minimal_variant()  # solves=None → inherit
        tech = _merge_variant(family, variant)
        assert tech.solves == ["MODERATE_STORAGE_GROWTH", "HIGH_STORAGE_GROWTH"]

    def test_variant_replaces_solves(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH", "HIGH_STORAGE_GROWTH"],
        )
        variant = _minimal_variant(solves=["HIGH_READ_LATENCY"])
        tech = _merge_variant(family, variant)
        assert tech.solves == ["HIGH_READ_LATENCY"]


# ---------------------------------------------------------------------------
# 5. Family-reference expansion in relationships
# ---------------------------------------------------------------------------

class TestFamilyRefExpansion:
    def test_family_ref_expands_to_variants(self):
        family_to_variants = {
            "compression": ["compression.lossless", "compression.lossy"],
            "caching": [],
        }
        refs = ["compression", "some_other"]
        expanded = _expand_family_refs(refs, family_to_variants)
        assert expanded == ["compression.lossless", "compression.lossy", "some_other"]

    def test_no_expansion_for_variant_ids(self):
        family_to_variants = {
            "compression": ["compression.lossless", "compression.lossy"],
        }
        refs = ["compression.lossless"]
        expanded = _expand_family_refs(refs, family_to_variants)
        assert expanded == ["compression.lossless"]

    def test_flatten_expands_synergies(self):
        fam_a = _minimal_family(
            id="fam_a",
            solves=["MODERATE_STORAGE_GROWTH"],
            synergies_with=["fam_b"],
            variants=[
                _minimal_variant(id="v1", name="A-V1"),
            ],
        )
        fam_b = _minimal_family(
            id="fam_b",
            solves=["HIGH_READ_LATENCY"],
            variants=[
                _minimal_variant(id="v1", name="B-V1"),
                _minimal_variant(id="v2", name="B-V2"),
            ],
        )
        techs = flatten([fam_a, fam_b])
        a_v1 = next(t for t in techs if t.id == "fam_a.v1")
        assert "fam_b.v1" in a_v1.synergies_with
        assert "fam_b.v2" in a_v1.synergies_with
        assert "fam_b" not in a_v1.synergies_with


# ---------------------------------------------------------------------------
# 6. Dangling-reference detection
# ---------------------------------------------------------------------------

class TestDanglingRefs:
    def test_dangling_solves_ref(self):
        family = _minimal_family(
            solves=["NOT_A_REAL_PROBLEM"],
        )
        with pytest.raises(KBIntegrityError) as exc_info:
            validate_kb([family])
        assert any("solves dangling" in v for v in exc_info.value.violations)

    def test_dangling_synergies_ref(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
            synergies_with=["nonexistent_family"],
        )
        with pytest.raises(KBIntegrityError) as exc_info:
            validate_kb([family])
        assert any("synergies_with dangling" in v for v in exc_info.value.violations)

    def test_valid_kb_passes(self):
        fam_a = _minimal_family(
            id="fam_a",
            solves=["MODERATE_STORAGE_GROWTH"],
            synergies_with=["fam_b"],
        )
        fam_b = _minimal_family(
            id="fam_b",
            solves=["HIGH_READ_LATENCY"],
        )
        validate_kb([fam_a, fam_b])


# ---------------------------------------------------------------------------
# 7. Duplicate-id detection
# ---------------------------------------------------------------------------

class TestDuplicateId:
    def test_duplicate_variant_ids(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
            variants=[
                _minimal_variant(id="dup", name="First"),
                _minimal_variant(id="dup", name="Second"),
            ],
        )
        with pytest.raises(KBIntegrityError) as exc_info:
            validate_kb([family])
        assert any("Duplicate effective id" in v for v in exc_info.value.violations)


# ---------------------------------------------------------------------------
# 8. Impact range rejection
# ---------------------------------------------------------------------------

class TestImpactRange:
    def test_valid_impacts(self):
        impacts = Impacts(storage=5, performance=-5, cost=0, scalability=3, security=-2)
        assert impacts.storage == 5
        assert impacts.performance == -5

    def test_impact_out_of_range(self):
        with pytest.raises(Exception):
            Impacts(storage=6)

    def test_negative_out_of_range(self):
        with pytest.raises(Exception):
            Impacts(performance=-6)


# ---------------------------------------------------------------------------
# 9. Graph edge kinds and directions
# ---------------------------------------------------------------------------

class TestProjectGraph:
    def test_solves_edges(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
        )
        techs = flatten([family])
        g = project_graph(techs)
        assert g.has_edge("test_fam", "MODERATE_STORAGE_GROWTH")
        assert g["test_fam"]["MODERATE_STORAGE_GROWTH"]["relation"] == "SOLVES"
        assert g.nodes["MODERATE_STORAGE_GROWTH"]["kind"] == "problem"
        assert g.nodes["test_fam"]["kind"] == "technique"

    def test_requires_directed(self):
        fam = _minimal_family(
            id="child",
            solves=["MODERATE_STORAGE_GROWTH"],
            requires=["parent"],
        )
        parent = _minimal_family(
            id="parent",
            solves=["HIGH_READ_LATENCY"],
        )
        techs = flatten([fam, parent])
        g = project_graph(techs)
        assert g.has_edge("child", "parent")
        assert g["child"]["parent"]["relation"] == "REQUIRES"

    def test_conflicts_bidirectional(self):
        fam_a = _minimal_family(
            id="a",
            solves=["MODERATE_STORAGE_GROWTH"],
            conflicts_with=["b"],
        )
        fam_b = _minimal_family(
            id="b",
            solves=["HIGH_READ_LATENCY"],
        )
        techs = flatten([fam_a, fam_b])
        g = project_graph(techs)
        assert g.has_edge("a", "b")
        assert g.has_edge("b", "a")
        assert g["a"]["b"]["relation"] == "CONFLICTS"
        assert g["a"]["b"]["undirected"] is True

    def test_synergizes_bidirectional(self):
        fam_a = _minimal_family(
            id="a",
            solves=["MODERATE_STORAGE_GROWTH"],
            synergies_with=["b"],
        )
        fam_b = _minimal_family(
            id="b",
            solves=["HIGH_READ_LATENCY"],
        )
        techs = flatten([fam_a, fam_b])
        g = project_graph(techs)
        assert g.has_edge("a", "b")
        assert g.has_edge("b", "a")
        assert g["a"]["b"]["relation"] == "SYNERGIZES"


# ---------------------------------------------------------------------------
# 10. flat_view() legacy-shape equivalence
# ---------------------------------------------------------------------------

class TestFlatView:
    def test_legacy_keys_present(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
            impacts=Impacts(storage=4, performance=1, cost=4, scalability=3, security=0),
            avoid_when=[AvoidWhen(condition="data already compressed", reason="waste")],
        )
        view = flat_view([family])
        assert len(view) == 1
        d = view[0]
        expected_keys = {
            "id", "name", "category", "description", "solves",
            "applicable_when", "conflicts_with", "benefits", "disadvantages",
            "implementation_complexity", "storage_impact", "performance_impact",
            "cost_impact", "scalability_impact", "prerequisites",
            "not_recommended_when",
        }
        assert set(d.keys()) == expected_keys

    def test_category_uppercased(self):
        family = _minimal_family(solves=["MODERATE_STORAGE_GROWTH"])
        view = flat_view([family])
        assert view[0]["category"] == "STORAGE"

    def test_impact_score_mapping(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
            impacts=Impacts(storage=5, performance=-2, cost=0, scalability=3, security=-1),
        )
        view = flat_view([family])
        d = view[0]
        assert d["storage_impact"] == "HIGH_IMPROVEMENT"
        assert d["performance_impact"] == "MODERATE_INCREASE"
        assert d["cost_impact"] == "NEUTRAL"
        assert d["scalability_impact"] == "MODERATE_IMPROVEMENT"

    def test_not_recommended_when_maps_avoid_when(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
            avoid_when=[
                AvoidWhen(condition="cond1", reason="r1"),
                AvoidWhen(condition="cond2", reason="r2"),
            ],
        )
        view = flat_view([family])
        assert view[0]["not_recommended_when"] == ["cond1", "cond2"]

    def test_pilot_families_produce_correct_count(self):
        kb_root = Path(__file__).resolve().parent.parent.parent / "src" / "storage_advisor" / "kb" / "techniques"
        families = discover_families(kb_root)
        view = flat_view(families)
        assert len(view) == 6  # compression: 4 variants + caching: 2 variants


# ---------------------------------------------------------------------------
# 11. Impacts deep-merge
# ---------------------------------------------------------------------------

class TestImpactsDeepMerge:
    def test_variant_overrides_single_impact_field(self):
        family = _minimal_family(
            impacts=Impacts(storage=4, performance=1, cost=4, scalability=3, security=0),
        )
        variant = _minimal_variant(
            impacts=Impacts(performance=-1),
        )
        tech = _merge_variant(family, variant)
        assert tech.impacts.storage == 4  # inherited
        assert tech.impacts.performance == -1  # overridden
        assert tech.impacts.cost == 4  # inherited


# ---------------------------------------------------------------------------
# 12. Schema version validation
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_rejects_version_1(self):
        with pytest.raises(Exception, match="Expected schema_version 2"):
            _minimal_family(schema_version=1)

    def test_accepts_version_2(self):
        fam = _minimal_family(schema_version=2)
        assert fam.schema_version == 2


# ---------------------------------------------------------------------------
# 13. Discover families from pilot YAML
# ---------------------------------------------------------------------------

class TestDiscoverFamilies:
    def test_discovers_pilot_families(self):
        kb_root = Path(__file__).resolve().parent.parent.parent / "src" / "storage_advisor" / "kb" / "techniques"
        families = discover_families(kb_root)
        ids = {f.id for f in families}
        assert "compression" in ids
        assert "caching" in ids
        assert len(families) == 2

    def test_flatten_pilot_families(self):
        kb_root = Path(__file__).resolve().parent.parent.parent / "src" / "storage_advisor" / "kb" / "techniques"
        techs = flatten(kb_root=kb_root)
        ids = {t.id for t in techs}
        assert "compression.lossless" in ids
        assert "compression.lossy" in ids
        assert "compression.adaptive" in ids
        assert "compression.delta" in ids
        assert "caching.read_cache" in ids
        assert "caching.write_behind" in ids
        assert len(techs) == 6


# ---------------------------------------------------------------------------
# 14. Validate pilot KB passes
# ---------------------------------------------------------------------------

class TestValidatePilot:
    def test_pilot_kb_valid(self):
        kb_root = Path(__file__).resolve().parent.parent.parent / "src" / "storage_advisor" / "kb" / "techniques"
        families = discover_families(kb_root)
        validate_kb(families)


# ---------------------------------------------------------------------------
# 15. KBIntegrityError collects all violations
# ---------------------------------------------------------------------------

class TestKBIntegrityErrorMultiple:
    def test_collects_multiple_violations(self):
        family = _minimal_family(
            solves=["FAKE_PROBLEM_1", "FAKE_PROBLEM_2"],
            synergies_with=["ghost_family"],
        )
        with pytest.raises(KBIntegrityError) as exc_info:
            validate_kb([family])
        assert len(exc_info.value.violations) >= 3
