# Recommendation Logic

How the engine turns a workload scenario into a prioritized architecture recommendation.

## Pipeline Overview

```
Scenario
  │
  ▼
Workload Profiling          classify raw numbers → discrete categories
  │
  ▼
Problem Detection           identify 12 architectural pressures
  │
  ▼
Candidate Generation        match problems → techniques from knowledge base
  │
  ▼
Rule Evaluation             score alignment, assign priority
  │
  ▼
Conflict Resolution         hard constraints → explicit conflicts → prerequisites
  │
  ▼
Strategy Construction       group into 7 workload-domain buckets
  │
  ▼
Impact Estimation           storage / cost / latency projections
```

## Stage 1: Workload Profiling

The profiler converts continuous scenario values into discrete classification buckets using **named threshold constants** (no magic numbers). This gives the rule engine stable categories to match against.

Example: `daily_growth_gb=150` → `storage_growth=HIGH` (threshold: >100 GB/day).

The profile has 11 classifications. See [domain_model.md](domain_model.md) for the full table.

## Stage 2: Problem Detection

12 detector functions each examine the scenario and profile to decide whether a specific architectural pressure is present. Each returns a `DetectedProblem` with:

- A severity (CRITICAL > HIGH > MEDIUM > LOW)
- Evidence (the field values that triggered it)
- Source fields (which scenario fields contributed)

Problems are returned sorted by severity (most severe first). This ordering drives the priority assignment in later stages.

### Problem Taxonomy

| Problem ID | Severity | Trigger |
|-----------|----------|---------|
| HIGH_AVAILABILITY_REQUIREMENT | CRITICAL | availability >= 99.99% |
| HIGH_STORAGE_GROWTH | HIGH | daily_growth > 100 GB |
| HIGH_READ_LATENCY | HIGH | read_intensity=HIGH + latency < 100ms |
| HIGH_WRITE_PRESSURE | HIGH | write_intensity=HIGH |
| LARGE_UNSTRUCTURED_OBJECT_WORKLOAD | HIGH | unstructured > 50% + unstructured data types |
| HIGH_ANALYTICS_WORKLOAD | MEDIUM | analytics_required + storage > 1TB |
| LONG_TERM_RETENTION | MEDIUM | retention > 5 years |
| HOT_COLD_DATA_MIX | MEDIUM | retention > 1yr + daily growth > 0 |
| LARGE_TRANSACTIONAL_DATASET | MEDIUM | TRANSACTIONS in data_types + storage > 1TB |
| DISASTER_RECOVERY_REQUIREMENT | MEDIUM | RTO < 60min or RPO < 30min |
| COMPLIANCE_REQUIREMENT | MEDIUM | any non-NONE compliance requirement |
| SCALABILITY_PRESSURE | MEDIUM | users > 1M + concurrent > 50K + growth > 100 GB |

## Stage 3: Candidate Generation

For each technique in the knowledge base, the generator checks whether any of the technique's `solves` problem IDs match a detected problem. If at least one matches, the technique becomes a candidate, paired with its list of matched problem IDs.

The knowledge base contains **19 techniques** in YAML (`configs/techniques.yaml`), each with:
- `solves`: which problem IDs it addresses
- `applicable_when`: profile conditions that make it relevant
- `prerequisites`: other techniques that must be present
- `conflicts_with`: incompatible techniques

## Stage 4: Rule Evaluation (Scoring)

Each candidate gets a deterministic **alignment score** (0.0-1.0):

```
alignment_score = 0.6 × problem_coverage + 0.4 × profile_alignment
```

### Problem Coverage Score (60% weight)

Measures what fraction of the total problem weight this technique solves:

```
coverage = Σ(severity_weight for matched problems) / Σ(severity_weight for all problems)
```

Severity weights: CRITICAL=1.0, HIGH=0.8, MEDIUM=0.5, LOW=0.2

### Profile Alignment Score (40% weight)

Measures how many of the technique's `applicable_when` conditions the current profile satisfies:

```
alignment = (matched conditions) / (total conditions)
```

If a technique has no `applicable_when` conditions, alignment defaults to 0.5.

### Priority Assignment

| Condition | Priority |
|-----------|----------|
| Solves a CRITICAL problem, OR solves a HIGH problem with score >= 0.7 | **REQUIRED** |
| Score >= 0.4 | **RECOMMENDED** |
| Otherwise | **OPTIONAL** |

## Stage 5: Conflict Resolution

Three filtering passes, applied in order:

### Pass 1: Hard Constraints

Techniques that are inappropriate for the scenario's scale are removed entirely:

| Technique | Hard Constraint |
|-----------|----------------|
| sharding | Excluded if expected_users < 1M **AND** storage < 1,000 GB |
| deduplication | Excluded if storage < 100 GB |

These are **rejections**, not score adjustments. The technique is completely removed.

### Pass 2: Explicit Conflicts

If technique A declares that it conflicts with technique B, and both are candidates:
- The one with the **higher alignment score** is kept
- The other is removed

Recommendations must be sorted by score descending before this pass (they are, from Stage 4).

### Pass 3: Prerequisite Enforcement

If technique A declares prerequisite B, and B is not in the surviving list:
- A is removed

Prerequisite chains in the knowledge base:
- `sharding` → requires `partitioning`
- `lifecycle_management` → requires `tiered_storage`
- `chunking` → requires `object_storage`

## Stage 6: Strategy Construction

Surviving recommendations are grouped into 7 workload-domain buckets. Each technique has a fixed bucket assignment (defined in `_STRATEGY_MAPPING`). Techniques not in any bucket go to `general`.

This gives the user a coherent architectural view rather than a flat list.

## Stage 7: Impact Estimation

See [assumptions.md](assumptions.md) for the full list of estimation constants.

Three dimensions are estimated:

### Storage Impact
Compounding reduction factors from compression, deduplication, columnar storage, and data pruning. Each technique multiplies the remaining storage by its assumed ratio.

### Cost Impact
Baseline: all data at hot-tier pricing ($0.023/GB/month). Optimized: reduced storage size, with cold-tier pricing ($0.004/GB/month) applied if tiered_storage or archiving is recommended.

### Latency Impact
Caching applies a weighted average (hit_rate × cache_latency + miss_rate × current_latency). Indexing and partitioning apply multiplicative speedup factors. These are mutually exclusive in the model (caching takes precedence).

All estimates are labeled **"MODEL-BASED ESTIMATE"** and carry explicit assumptions.
