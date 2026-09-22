# Knowledge Base v2

## Purpose and File Layout

KB v2 provides a **family/variant schema** for technique definitions,
replacing the flat list with a hierarchical model where a technique
family defines shared properties and variants inherit from and
selectively override them.

```
kb/
├── __init__.py
├── schema.py          # Pydantic v2 models
├── loader.py          # YAML discovery, merge, flatten, graph
├── validate.py        # Integrity checks (violations + warnings)
├── compat.py          # flat_view() → legacy-shaped dicts
├── provider.py        # get_techniques() — single engine entry point
└── techniques/
    └── <category>/
        └── <family>.yaml    # schema_version: 2
```

Each YAML file lives at `kb/techniques/<category>/<family>.yaml` and
must set `schema_version: 2` at the top level.

---

## Field Reference

### Family (top-level YAML)

| Field | Type | Required | Default |
|---|---|---|---|
| `schema_version` | int | yes | — (must be 2) |
| `id` | str | yes | — |
| `name` | str | yes | — |
| `category` | FamilyCategory enum | yes | — |
| `summary` | str | yes | — |
| `mechanism` | str | no | None |
| `solves` | list[str] | no | [] |
| `synergies_with` | list[str] | no | [] |
| `conflicts_with` | list[str] | no | [] |
| `requires` | list[str] | no | [] |
| `avoid_when` | list[AvoidWhen] | no | [] |
| `applicable_when` | dict[str, list[str]] | no | {} |
| `implementation_complexity` | Complexity enum | no | medium |
| `impacts` | Impacts | no | all zeros |
| `benefits` | list[str] | no | [] |
| `disadvantages` | list[str] | no | [] |
| `companies` | list[Company] | no | [] |
| `variants` | list[Variant] | no | [] |

### Variant (nested under `variants:`)

Same fields as Family except `schema_version`, `category`, and
`variants` are absent.  All fields except `id` and `name` are
optional — `None` means "inherit from the parent family."

### Impacts

Signed impact scores from **-5** (severe overhead) to **+5** (major
improvement).  Negative values explicitly declare that a technique
introduces overhead in that dimension.

| Field | Range |
|---|---|
| `storage` | -5 .. +5 |
| `performance` | -5 .. +5 |
| `cost` | -5 .. +5 |
| `scalability` | -5 .. +5 |
| `security` | -5 .. +5 |

### AvoidWhen

| Field | Type |
|---|---|
| `condition` | str — when this technique should NOT be used |
| `reason` | str — why (always required) |

### Company

| Field | Type |
|---|---|
| `name` | str — company name |
| `context` | str — how they use this technique |

---

## Merge Semantics

When a family has variants, each variant inherits from the family and
can selectively override.  The merge rules, applied uniformly at every
nesting depth:

1. **Dicts** deep-merge recursively — variant keys override, family
   keys not present in the variant are kept.
2. **Lists** replace wholly — a variant that sets a list field replaces
   the entire family list (it does not append).  To extend a family
   list, the variant must restate the full list.
3. **Scalars** override — a non-None variant value replaces the family
   value.  `None` means "inherit."

All merge functions are **pure**: they never mutate Family or Variant
inputs.

### Worked Example: applicable_when

```yaml
# Family
applicable_when:
  storage_growth: [MEDIUM, HIGH]
  latency_class: [LOW_LATENCY]

# Variant
applicable_when:
  storage_growth: [EXTREME]    # replaces the inner list
  data_type: [MEDIA]           # new key added
```

Result after merge:

```yaml
applicable_when:
  storage_growth: [EXTREME]     # replaced (list semantics)
  latency_class: [LOW_LATENCY]  # inherited (key not in variant)
  data_type: [MEDIA]            # added (new key)
```

---

## Relationship Policies

### Edge Kinds

| Relation | Direction | Graph storage |
|---|---|---|
| SOLVES | technique → problem | directed edge |
| REQUIRES | technique → technique | directed edge |
| CONFLICTS | technique ↔ technique | one edge, canonical sorted(a,b) order |
| SYNERGIZES | technique ↔ technique | one edge, canonical sorted(a,b) order |

### Family-Reference Expansion

Relationship fields (`synergies_with`, `conflicts_with`, `requires`)
may reference a family id.  At **flatten time**, any family id that has
variants is expanded to all its variant ids.

> **This expansion is a flatten-time SNAPSHOT.**  If the referenced
> family later gains new variants (e.g. a new YAML variant is added),
> the expansion results change on the next `flatten()` call.  Edges in
> a previously built graph are NOT updated automatically.

### Asymmetry = Warning

If technique A declares `synergies_with: [B]` but B does not declare
`synergies_with: [A]`, this is reported as a **non-fatal warning** in
the `KBReport` returned by `validate_kb()`.  Same for `conflicts_with`.

### Mutual Declaration = Single Edge

When both sides declare the same relationship (e.g. A conflicts_with B
AND B conflicts_with A), `project_graph()` produces exactly **one**
edge with canonical endpoint order `(min(A,B), max(A,B))`.

### REQUIRES Cycles Forbidden

Any directed cycle in the REQUIRES subgraph (after family-reference
expansion) is a **fatal violation**.  Detected via networkx cycle
detection in `validate_kb()`.

### Self-References Forbidden

Any relationship field (solves excluded) that resolves to `src == dst`
after expansion is a fatal violation.  Family-level self-lists (e.g.
family "foo" listing "foo" in its own `synergies_with`) are likewise
forbidden.

---

## ID Conventions

- **Family id**: lowercase, underscore-separated (e.g. `compression`,
  `read_replica`).
- **Variant id**: lowercase, underscore-separated (e.g. `lossless`,
  `write_behind`).
- **Effective technique id**: `<family_id>.<variant_id>` (e.g.
  `compression.lossless`).  A family with no variants uses the bare
  family id.

### Enums

- **FamilyCategory**: `storage`, `database`, `performance`, `analytics`,
  `reliability`, `architecture`, `security`
- **Complexity**: `low`, `medium`, `high`

---

## Provider Seam

`kb/provider.py` exposes `get_techniques() -> list[dict]`, the single
entry point for the recommendation engine.  It unions legacy YAML
entries with v2 `flat_view()` output:

1. Load all entries from `configs/techniques.yaml` (the legacy registry).
2. Load all effective techniques from v2 `flat_view()`.
3. For each legacy entry, substitute the v2 version if an exact ID
   match exists (**v2 wins** on collision).
4. v2-only entries (no matching legacy ID) are excluded from the
   engine-visible set.

`knowledge/technique_catalog.py`'s `load_techniques()` calls the
provider, making this the only KB access seam for the engine.

### Legacy Coexistence

The legacy YAML (`configs/techniques.yaml`) remains as the engine's
**technique registry** — it defines the set of 19 IDs the engine
operates on.  All 19 legacy techniques also exist as v2 families;
the provider substitutes the richer v2 content at load time.

v2-only families (backup_strategies, multi_region, encryption, masking,
compaction, file_format_optimization, bloom_filters) are NOT
engine-visible until explicitly registered in the legacy YAML.

The v2 `security` impact dimension is dropped by `flat_view()` because
the legacy schema has no security impact field.

---

## Authoring Checklist for New Technique Families

- [ ] `summary` and `mechanism` written in plain language; summary is
      what it does, mechanism is how.
- [ ] `solves` mapped to **existing** ProblemId enum values only; do
      not invent new problem ids without updating the domain model.
- [ ] At least one `synergies_with` or `conflicts_with` entry, with a
      rationale in `avoid_when`-style prose or YAML comments explaining
      why the relationship exists.
- [ ] Every `avoid_when` entry carries both `condition` and `reason`.
- [ ] `impacts` scored honestly, including **negative overheads** —
      e.g. a caching technique should declare `cost: -2` if it adds
      infrastructure cost.
- [ ] `companies` limited to well-documented, public examples with
      `context` explaining how they use the technique (not just "uses
      it").
- [ ] `implementation_complexity` rated by **operational burden** (how
      hard to run in production), not code size or cleverness.
- [ ] All variants have unique `id` values within the family.
- [ ] Run `validate_kb()` after authoring and fix all violations;
      review warnings.

---

## Running Validation and Tests

### Validate the KB programmatically

```python
from storage_advisor.kb.validate import validate_kb

report = validate_kb()  # discovers from default kb/techniques/
print(f"Warnings: {report.warnings}")
# Raises KBIntegrityError if any violations exist
```

### Run the test suite

```bash
# All tests (legacy + KB v2)
pytest -q

# KB v2 tests only
pytest tests/kb/ -v
```
