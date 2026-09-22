"""Tests for KB v2: schema, loader, validate, compat, and provider modules."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from storage_advisor.kb.compat import flat_view
from storage_advisor.kb.loader import (
    _deep_merge_dict,
    _expand_family_refs,
    _merge_variant,
    discover_families,
    flatten,
    project_graph,
)
from storage_advisor.kb.provider import get_techniques
from storage_advisor.kb.schema import AvoidWhen, Complexity, Family, Impacts, Variant
from storage_advisor.kb.validate import KBIntegrityError, KBReport, validate_kb

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_family(**overrides) -> Family:
    defaults = {
        "schema_version": 2,
        "id": "test_fam",
        "name": "Test Family",
        "category": "storage",
        "summary": "A test family",
        "mechanism": "Does things",
    }
    defaults.update(overrides)
    return Family(**defaults)


def _minimal_variant(**overrides) -> Variant:
    defaults = {"id": "var1", "name": "Variant 1"}
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
        family = _minimal_family(benefits=["family benefit 1"])
        variant = _minimal_variant()
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
        variant = _minimal_variant()
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
        assert expanded == [
            "compression.lossless", "compression.lossy", "some_other",
        ]

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
            variants=[_minimal_variant(id="v1", name="A-V1")],
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
        family = _minimal_family(solves=["NOT_A_REAL_PROBLEM"])
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
        assert any(
            "synergies_with dangling" in v for v in exc_info.value.violations
        )

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
        report = validate_kb([fam_a, fam_b])
        assert isinstance(report, KBReport)
        assert not report.violations


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
        assert any(
            "Duplicate effective id" in v for v in exc_info.value.violations
        )


# ---------------------------------------------------------------------------
# 8. Impact range rejection
# ---------------------------------------------------------------------------

class TestImpactRange:
    def test_valid_impacts(self):
        impacts = Impacts(
            storage=5, performance=-5, cost=0, scalability=3, security=-2,
        )
        assert impacts.storage == 5
        assert impacts.performance == -5

    def test_impact_out_of_range(self):
        with pytest.raises(ValidationError):
            Impacts(storage=6)

    def test_negative_out_of_range(self):
        with pytest.raises(ValidationError):
            Impacts(performance=-6)


# ---------------------------------------------------------------------------
# 9. Graph edge kinds and directions
# ---------------------------------------------------------------------------

class TestProjectGraph:
    def test_solves_edges(self):
        family = _minimal_family(solves=["MODERATE_STORAGE_GROWTH"])
        techs = flatten([family])
        g = project_graph(techs)
        assert g.has_edge("test_fam", "MODERATE_STORAGE_GROWTH")
        edge = g["test_fam"]["MODERATE_STORAGE_GROWTH"]
        assert edge["relation"] == "SOLVES"
        assert g.nodes["MODERATE_STORAGE_GROWTH"]["kind"] == "problem"
        assert g.nodes["test_fam"]["kind"] == "technique"

    def test_requires_directed(self):
        fam = _minimal_family(
            id="child",
            solves=["MODERATE_STORAGE_GROWTH"],
            requires=["parent"],
        )
        parent = _minimal_family(
            id="parent", solves=["HIGH_READ_LATENCY"],
        )
        techs = flatten([fam, parent])
        g = project_graph(techs)
        assert g.has_edge("child", "parent")
        assert g["child"]["parent"]["relation"] == "REQUIRES"

    def test_conflicts_canonical_edge(self):
        fam_a = _minimal_family(
            id="a",
            solves=["MODERATE_STORAGE_GROWTH"],
            conflicts_with=["b"],
        )
        fam_b = _minimal_family(
            id="b", solves=["HIGH_READ_LATENCY"],
        )
        techs = flatten([fam_a, fam_b])
        g = project_graph(techs)
        assert g.has_edge("a", "b")
        assert g["a"]["b"]["relation"] == "CONFLICTS"
        assert g["a"]["b"]["undirected"] is True

    def test_synergizes_canonical_edge(self):
        fam_a = _minimal_family(
            id="a",
            solves=["MODERATE_STORAGE_GROWTH"],
            synergies_with=["b"],
        )
        fam_b = _minimal_family(
            id="b", solves=["HIGH_READ_LATENCY"],
        )
        techs = flatten([fam_a, fam_b])
        g = project_graph(techs)
        assert g.has_edge("a", "b")
        assert g["a"]["b"]["relation"] == "SYNERGIZES"
        assert g["a"]["b"]["undirected"] is True


# ---------------------------------------------------------------------------
# 10. flat_view() legacy-shape equivalence
# ---------------------------------------------------------------------------

class TestFlatView:
    def test_legacy_keys_present(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
            impacts=Impacts(
                storage=4, performance=1, cost=4, scalability=3, security=0,
            ),
            avoid_when=[
                AvoidWhen(condition="data already compressed", reason="waste"),
            ],
        )
        view = flat_view([family])
        assert len(view) == 1
        d = view[0]
        expected_keys = {
            "id", "name", "category", "description", "solves",
            "applicable_when", "conflicts_with", "benefits", "disadvantages",
            "implementation_complexity", "storage_impact",
            "performance_impact", "cost_impact", "scalability_impact",
            "prerequisites", "not_recommended_when",
        }
        assert set(d.keys()) == expected_keys

    def test_category_uppercased(self):
        family = _minimal_family(solves=["MODERATE_STORAGE_GROWTH"])
        view = flat_view([family])
        assert view[0]["category"] == "STORAGE"

    def test_impact_score_mapping(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
            impacts=Impacts(
                storage=5, performance=-2, cost=0, scalability=3, security=-1,
            ),
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

    def test_all_families_produce_correct_count(self):
        kb_root = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "storage_advisor" / "kb" / "techniques"
        )
        families = discover_families(kb_root)
        view = flat_view(families)
        assert len(view) == 35


# ---------------------------------------------------------------------------
# 11. Impacts deep-merge
# ---------------------------------------------------------------------------

class TestImpactsDeepMerge:
    def test_variant_overrides_single_impact_field(self):
        family = _minimal_family(
            impacts=Impacts(
                storage=4, performance=1, cost=4, scalability=3, security=0,
            ),
        )
        variant = _minimal_variant(impacts=Impacts(performance=-1))
        tech = _merge_variant(family, variant)
        assert tech.impacts.storage == 4
        assert tech.impacts.performance == -1
        assert tech.impacts.cost == 4


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
    def test_discovers_all_families(self):
        kb_root = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "storage_advisor" / "kb" / "techniques"
        )
        families = discover_families(kb_root)
        ids = {f.id for f in families}
        assert "compression" in ids
        assert "caching" in ids
        assert "deduplication" in ids
        assert "partitioning" in ids
        assert "backup_strategies" in ids
        assert "multi_region" in ids
        assert "encryption" in ids
        assert "bloom_filters" in ids
        assert len(families) == 26

    def test_flatten_all_families(self):
        kb_root = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "storage_advisor" / "kb" / "techniques"
        )
        techs = flatten(kb_root=kb_root)
        ids = {t.id for t in techs}
        assert "compression.lossless" in ids
        assert "caching.read_cache" in ids
        assert "deduplication" in ids
        assert "partitioning" in ids
        assert "backup_strategies.snapshots" in ids
        assert "multi_region.active_active" in ids
        assert "encryption.at_rest" in ids
        assert "bloom_filters" in ids
        assert len(techs) == 35


# ---------------------------------------------------------------------------
# 14. Validate pilot KB passes
# ---------------------------------------------------------------------------

class TestValidatePilot:
    def test_pilot_kb_valid(self):
        kb_root = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "storage_advisor" / "kb" / "techniques"
        )
        families = discover_families(kb_root)
        report = validate_kb(families)
        assert isinstance(report, KBReport)
        assert not report.violations


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


# ---------------------------------------------------------------------------
# 16. Nested merge: applicable_when deep-merges (D.11)
# ---------------------------------------------------------------------------

class TestNestedMerge:
    def test_applicable_when_deep_merges(self):
        family = _minimal_family(
            applicable_when={
                "storage_growth": ["MEDIUM", "HIGH"],
                "latency_class": ["LOW_LATENCY"],
            },
        )
        variant = _minimal_variant(
            applicable_when={
                "storage_growth": ["EXTREME"],
                "data_type": ["MEDIA"],
            },
        )
        tech = _merge_variant(family, variant)
        assert tech.applicable_when == {
            "storage_growth": ["EXTREME"],
            "latency_class": ["LOW_LATENCY"],
            "data_type": ["MEDIA"],
        }


# ---------------------------------------------------------------------------
# 17. Purity: inputs unchanged after merge/flatten (D.12)
# ---------------------------------------------------------------------------

class TestPurity:
    def test_merge_does_not_mutate_inputs(self):
        family = _minimal_family(
            benefits=["fam benefit"],
            solves=["MODERATE_STORAGE_GROWTH"],
            impacts=Impacts(
                storage=4, performance=1, cost=4, scalability=3, security=0,
            ),
        )
        variant = _minimal_variant(
            benefits=["var benefit"],
            impacts=Impacts(performance=-1),
        )
        family_dump = family.model_dump()
        variant_dump = variant.model_dump()

        _merge_variant(family, variant)

        assert family.model_dump() == family_dump
        assert variant.model_dump() == variant_dump

    def test_flatten_does_not_mutate_families(self):
        fam = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
            synergies_with=["other"],
            variants=[_minimal_variant(id="v1", name="V1")],
        )
        other = _minimal_family(
            id="other", solves=["HIGH_READ_LATENCY"],
        )
        fam_dump = fam.model_dump()
        flatten([fam, other])
        assert fam.model_dump() == fam_dump


# ---------------------------------------------------------------------------
# 18. Frozen EffectiveTechnique (D.13)
# ---------------------------------------------------------------------------

class TestFrozen:
    def test_assignment_raises(self):
        family = _minimal_family(solves=["MODERATE_STORAGE_GROWTH"])
        techs = flatten([family])
        tech = techs[0]
        with pytest.raises(ValidationError):
            tech.name = "changed"


# ---------------------------------------------------------------------------
# 19. REQUIRES cycle detection (D.14)
# ---------------------------------------------------------------------------

class TestCycle:
    def test_requires_cycle_detected(self):
        fam_a = _minimal_family(
            id="a",
            solves=["MODERATE_STORAGE_GROWTH"],
            requires=["b"],
        )
        fam_b = _minimal_family(
            id="b",
            solves=["HIGH_READ_LATENCY"],
            requires=["a"],
        )
        with pytest.raises(KBIntegrityError) as exc_info:
            validate_kb([fam_a, fam_b])
        assert any(
            "REQUIRES cycle" in v for v in exc_info.value.violations
        )


# ---------------------------------------------------------------------------
# 20. Self-reference detection (D.15)
# ---------------------------------------------------------------------------

class TestSelfReference:
    def test_self_in_conflicts_with(self):
        family = _minimal_family(
            solves=["MODERATE_STORAGE_GROWTH"],
            conflicts_with=["test_fam"],
        )
        with pytest.raises(KBIntegrityError) as exc_info:
            validate_kb([family])
        assert any(
            "self-reference" in v for v in exc_info.value.violations
        )


# ---------------------------------------------------------------------------
# 21. Asymmetric relationship warning (D.16)
# ---------------------------------------------------------------------------

class TestAsymmetry:
    def test_one_sided_synergy_warns(self):
        fam_a = _minimal_family(
            id="alpha",
            solves=["MODERATE_STORAGE_GROWTH"],
            synergies_with=["beta"],
        )
        fam_b = _minimal_family(
            id="beta", solves=["HIGH_READ_LATENCY"],
        )
        report = validate_kb([fam_a, fam_b])
        assert isinstance(report, KBReport)
        assert len(report.warnings) == 1
        assert "Asymmetric synergy" in report.warnings[0]
        assert "alpha" in report.warnings[0]
        assert "beta" in report.warnings[0]

        techs = flatten([fam_a, fam_b])
        g = project_graph(techs)
        syn_edges = [
            (u, v)
            for u, v, d in g.edges(data=True)
            if d["relation"] == "SYNERGIZES"
        ]
        assert len(syn_edges) == 1


# ---------------------------------------------------------------------------
# 22. Duplicate edge dedup (D.17)
# ---------------------------------------------------------------------------

class TestDedupe:
    def test_mutual_conflict_yields_one_edge(self):
        fam_a = _minimal_family(
            id="a",
            solves=["MODERATE_STORAGE_GROWTH"],
            conflicts_with=["b"],
        )
        fam_b = _minimal_family(
            id="b",
            solves=["HIGH_READ_LATENCY"],
            conflicts_with=["a"],
        )
        techs = flatten([fam_a, fam_b])
        g = project_graph(techs)
        conflicts = [
            (u, v)
            for u, v, d in g.edges(data=True)
            if d["relation"] == "CONFLICTS"
        ]
        assert len(conflicts) == 1
        assert conflicts[0] == ("a", "b")


# ---------------------------------------------------------------------------
# 23. Determinism (D.18)
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_flatten_twice_same_ids(self):
        fam_a = _minimal_family(
            id="alpha",
            solves=["MODERATE_STORAGE_GROWTH"],
            variants=[
                _minimal_variant(id="v1", name="V1"),
                _minimal_variant(id="v2", name="V2"),
            ],
        )
        fam_b = _minimal_family(
            id="beta", solves=["HIGH_READ_LATENCY"],
        )
        ids_1 = [t.id for t in flatten([fam_a, fam_b])]
        ids_2 = [t.id for t in flatten([fam_a, fam_b])]
        assert ids_1 == ids_2

    def test_full_kb_order_matches_sorted_paths(self):
        kb_root = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "storage_advisor" / "kb" / "techniques"
        )
        techs = flatten(kb_root=kb_root)
        ids = [t.id for t in techs]
        expected = [
            # analytics/
            "columnar_storage", "data_aggregation", "parquet_format",
            # architecture/
            "multi_region.active_passive", "multi_region.active_active",
            # database/
            "indexing", "partitioning", "replication",
            "schema_optimization", "sharding",
            # performance/
            "bloom_filters",
            "caching.read_cache", "caching.write_behind",
            "data_pruning", "materialized_views", "query_optimization",
            # reliability/
            "backup_strategies.snapshots",
            "backup_strategies.continuous_backup_pitr",
            # security/
            "encryption.at_rest", "encryption.in_transit",
            "masking.static", "masking.dynamic",
            # storage/
            "archiving", "chunking", "compaction",
            "compression.lossless", "compression.lossy",
            "compression.adaptive", "compression.delta",
            "deduplication",
            "file_format_optimization.parquet",
            "file_format_optimization.orc",
            "lifecycle_management",
            "object_storage", "tiered_storage",
        ]
        assert ids == expected


# ---------------------------------------------------------------------------
# 24. Provider: v2 wins on collision
# ---------------------------------------------------------------------------

class TestProviderV2Wins:
    def test_v2_substitutes_matching_id(self, tmp_path, monkeypatch):
        legacy_yaml = {
            "techniques": [
                {"id": "dedup", "name": "Legacy Dedup", "category": "STORAGE"},
                {"id": "other", "name": "Other Tech", "category": "DATABASE"},
            ],
        }
        legacy_path = tmp_path / "techniques.yaml"
        legacy_path.write_text(yaml.dump(legacy_yaml))

        v2_entry = {"id": "dedup", "name": "V2 Dedup", "category": "STORAGE"}
        monkeypatch.setattr(
            "storage_advisor.kb.provider.flat_view", lambda: [v2_entry],
        )

        result = get_techniques(legacy_path=legacy_path)
        dedup = next(e for e in result if e["id"] == "dedup")
        assert dedup["name"] == "V2 Dedup"
        assert len(result) == 2

    def test_count_preserved_on_collision(self, tmp_path, monkeypatch):
        legacy_yaml = {
            "techniques": [
                {"id": "a", "name": "A"},
                {"id": "b", "name": "B"},
                {"id": "c", "name": "C"},
            ],
        }
        legacy_path = tmp_path / "techniques.yaml"
        legacy_path.write_text(yaml.dump(legacy_yaml))

        v2_entries = [
            {"id": "a", "name": "V2-A"},
            {"id": "b", "name": "V2-B"},
        ]
        monkeypatch.setattr(
            "storage_advisor.kb.provider.flat_view", lambda: v2_entries,
        )

        result = get_techniques(legacy_path=legacy_path)
        assert len(result) == 3
        assert result[0]["name"] == "V2-A"
        assert result[1]["name"] == "V2-B"
        assert result[2]["name"] == "C"


# ---------------------------------------------------------------------------
# 25. Provider: unmigrated legacy still served
# ---------------------------------------------------------------------------

class TestProviderLegacyPassthrough:
    def test_legacy_entries_pass_through_when_no_v2_match(
        self, tmp_path, monkeypatch,
    ):
        legacy_yaml = {
            "techniques": [
                {"id": "legacy_only", "name": "Legacy Only", "category": "STORAGE"},
            ],
        }
        legacy_path = tmp_path / "techniques.yaml"
        legacy_path.write_text(yaml.dump(legacy_yaml))

        monkeypatch.setattr(
            "storage_advisor.kb.provider.flat_view", list,
        )

        result = get_techniques(legacy_path=legacy_path)
        assert len(result) == 1
        assert result[0]["id"] == "legacy_only"
        assert result[0]["name"] == "Legacy Only"

    def test_v2_only_entries_excluded(self, tmp_path, monkeypatch):
        legacy_yaml = {"techniques": [{"id": "a", "name": "A"}]}
        legacy_path = tmp_path / "techniques.yaml"
        legacy_path.write_text(yaml.dump(legacy_yaml))

        monkeypatch.setattr(
            "storage_advisor.kb.provider.flat_view",
            lambda: [{"id": "v2_only", "name": "V2 Only"}],
        )

        result = get_techniques(legacy_path=legacy_path)
        assert len(result) == 1
        assert result[0]["id"] == "a"


# ---------------------------------------------------------------------------
# 26. Provider: returned records pass legacy-shape contract
# ---------------------------------------------------------------------------

class TestProviderLegacyShape:
    def test_v2_substituted_entry_has_legacy_keys(self, tmp_path, monkeypatch):
        legacy_yaml = {
            "techniques": [{"id": "test_tech", "name": "Old Name"}],
        }
        legacy_path = tmp_path / "techniques.yaml"
        legacy_path.write_text(yaml.dump(legacy_yaml))

        v2_entry = {
            "id": "test_tech",
            "name": "New Name",
            "category": "STORAGE",
            "description": "A summary",
            "solves": ["MODERATE_STORAGE_GROWTH"],
            "applicable_when": {"storage_growth": ["HIGH"]},
            "conflicts_with": [],
            "benefits": ["saves space"],
            "disadvantages": ["cpu cost"],
            "implementation_complexity": "MEDIUM",
            "storage_impact": "HIGH_IMPROVEMENT",
            "performance_impact": "SLIGHT_INCREASE",
            "cost_impact": "MODERATE_IMPROVEMENT",
            "scalability_impact": "NEUTRAL",
            "prerequisites": [],
            "not_recommended_when": ["already compressed"],
        }
        monkeypatch.setattr(
            "storage_advisor.kb.provider.flat_view", lambda: [v2_entry],
        )

        result = get_techniques(legacy_path=legacy_path)
        d = result[0]
        expected_keys = {
            "id", "name", "category", "description", "solves",
            "applicable_when", "conflicts_with", "benefits", "disadvantages",
            "implementation_complexity", "storage_impact",
            "performance_impact", "cost_impact", "scalability_impact",
            "prerequisites", "not_recommended_when",
        }
        assert expected_keys.issubset(set(d.keys()))


# ---------------------------------------------------------------------------
# 27. Provider: live integration (no mocks)
# ---------------------------------------------------------------------------

class TestProviderIntegration:
    def test_live_provider_returns_19_techniques(self):
        result = get_techniques()
        assert len(result) == 19

    def test_live_provider_all_have_id_field(self):
        result = get_techniques()
        for entry in result:
            assert "id" in entry
            assert isinstance(entry["id"], str)

    def test_live_provider_no_duplicate_ids(self):
        result = get_techniques()
        ids = [e["id"] for e in result]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# 28. Full KB validation: zero violations
# ---------------------------------------------------------------------------

class TestFullKBValidation:
    def test_zero_violations(self):
        families = discover_families()
        report = validate_kb(families)
        assert not report.violations, f"Unexpected violations: {report.violations}"

    def test_all_families_load(self):
        families = discover_families()
        assert len(families) >= 21


# ---------------------------------------------------------------------------
# 29. Warnings snapshot
# ---------------------------------------------------------------------------

class TestWarningsSnapshot:
    def test_warnings_match_snapshot(self):
        import json

        snapshot_path = Path(__file__).parent / "warnings_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text())

        families = discover_families()
        report = validate_kb(families)

        assert sorted(report.warnings) == snapshot["warnings"]
        assert report.violations == snapshot["violations"]


# ---------------------------------------------------------------------------
# 30. Per-family checklist guard
# ---------------------------------------------------------------------------

_REQUIRED_FAMILY_FIELDS = {
    "id", "name", "category", "summary", "mechanism",
    "solves", "avoid_when", "impacts", "benefits", "disadvantages",
}


class TestFamilyChecklist:
    def test_every_family_has_required_fields(self):
        families = discover_families()
        for fam in families:
            dump = fam.model_dump()
            missing = _REQUIRED_FAMILY_FIELDS - set(dump.keys())
            assert not missing, f"{fam.id} missing fields: {missing}"

    def test_every_family_has_at_least_one_solve(self):
        families = discover_families()
        for fam in families:
            assert fam.solves, f"{fam.id} has no solves"

    def test_every_family_has_at_least_one_avoid_when(self):
        families = discover_families()
        for fam in families:
            assert fam.avoid_when, f"{fam.id} has no avoid_when"

    def test_every_family_has_mechanism(self):
        families = discover_families()
        for fam in families:
            assert fam.mechanism, f"{fam.id} has no mechanism"

    def test_no_impact_exceeds_bounds(self):
        families = discover_families()
        for fam in families:
            for field in ("storage", "performance", "cost", "scalability", "security"):
                val = getattr(fam.impacts, field)
                assert -5 <= val <= 5, f"{fam.id} impacts.{field} = {val}"
