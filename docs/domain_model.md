# Domain Model

The core data types that flow through the recommendation pipeline.

## Scenario (Input)

A `Scenario` is the complete, validated description of a user's data-storage workload. It is the sole input to the pipeline — every downstream decision traces back to one or more scenario fields.

### Fields

| Field | Type | Constraint | Description |
|-------|------|-----------|-------------|
| `business_domain` | BusinessDomain | enum, 18 values | Industry vertical (AI, HEALTHCARE, FINTECH, etc.) |
| `company_size` | CompanySize | enum | STARTUP / SMALL / MEDIUM / LARGE / ENTERPRISE |
| `expected_users` | int | >= 1 | Total expected user population |
| `concurrent_users` | int | >= 1, <= expected_users | Simultaneous active users |
| `current_storage_gb` | float | > 0 | Current stored data in GB |
| `daily_growth_gb` | float | >= 0 | New data per day in GB |
| `data_types` | list[DataType] | min 1 element | Data types present in the workload |
| `structured_data_pct` | float | 0-100 | % of data that is structured |
| `semi_structured_data_pct` | float | 0-100 | % of data that is semi-structured |
| `unstructured_data_pct` | float | 0-100 | % of data that is unstructured |
| `read_intensity` | Intensity | LOW/MEDIUM/HIGH | Read workload intensity |
| `write_intensity` | Intensity | LOW/MEDIUM/HIGH | Write workload intensity |
| `access_pattern` | AccessPattern | RANDOM/SEQUENTIAL/MIXED | How data is accessed |
| `latency_requirement_ms` | float | > 0 | Max acceptable latency in ms |
| `availability_requirement` | float | 90-100 | Target availability as % |
| `rto_minutes` | float | >= 0 | Recovery Time Objective |
| `rpo_minutes` | float | >= 0 | Recovery Point Objective |
| `retention_years` | float | >= 0 | How long data must be retained |
| `budget_level` | BudgetLevel | LOW/MEDIUM/HIGH | Budget constraint level |
| `analytics_required` | bool | | Whether analytics workloads are needed |
| `real_time_processing_required` | bool | | Whether real-time processing is needed |
| `sensitive_data` | bool | | Whether data contains sensitive information |
| `encryption_required` | bool | | Whether encryption is mandatory |
| `compliance_requirements` | list[ComplianceType] | | NONE, HIPAA, GDPR, SOC2, PCI_DSS |

### Validation Rules

1. **concurrent_users <= expected_users** — cannot have more simultaneous users than total users.
2. **Data percentages sum to 100** — `structured + semi_structured + unstructured` must equal 100.0 (tolerance: ±0.01).
3. **Case-insensitive enum matching** — all enum fields accept any casing (e.g. "high", "High", "HIGH").
4. **Domain aliases** — common alternate spellings are normalized: `e-commerce` → `ECOMMERCE`, `fin-tech` → `FINTECH`, `telecom` → `TELECOMMUNICATION`, `pci` → `PCI_DSS`.

### Enums

**BusinessDomain** (18 values): ECOMMERCE, FINTECH, HEALTHCARE, MEDIA, SAAS, IOT, GAMING, EDUCATION, GOVERNMENT, MANUFACTURING, LOGISTICS, RETAIL, TELECOMMUNICATION, AGRICULTURE, ENERGY, RESEARCH, AI, OTHER

**DataType** (13 values): TEXT, IMAGES, VIDEOS, AUDIO, DOCUMENTS, TRANSACTIONS, LOGS, SENSOR_DATA, TIME_SERIES, GPS_DATA, CLICKSTREAM, EMBEDDINGS, ML_FEATURES

**ComplianceType** (5 values): NONE, HIPAA, GDPR, SOC2, PCI_DSS

## WorkloadProfile (Internal)

The workload profiler classifies the raw scenario numbers into discrete categories using named threshold constants. This converts continuous values into meaningful buckets the rule engine can match against.

| Classification | Values | Key Thresholds |
|---------------|--------|----------------|
| `storage_growth` | LOW / MEDIUM / HIGH | <= 10 GB/day, <= 100 GB/day, > 100 GB/day |
| `read_pressure` | LOW / MEDIUM / HIGH | Based on read_intensity + concurrent_users |
| `write_pressure` | LOW / MEDIUM / HIGH | Based on write_intensity + concurrent_users |
| `latency_class` | RELAXED / MODERATE / LOW_LATENCY / ULTRA_LOW_LATENCY | > 500ms, > 100ms, > 20ms, <= 20ms |
| `retention_class` | SHORT_TERM / MEDIUM_TERM / LONG_TERM | <= 1yr, <= 5yr, > 5yr |
| `availability_class` | STANDARD / HIGH / VERY_HIGH / MISSION_CRITICAL | < 99.9%, >= 99.9%, >= 99.99%, >= 99.999% |
| `compliance_pressure` | NONE / PRESENT | Any non-NONE compliance requirement |
| `object_storage_pressure` | LOW / MEDIUM / HIGH | Based on unstructured_data_pct + data_types |
| `analytics_pressure` | LOW / MEDIUM / HIGH | Based on analytics_required + storage size |
| `concurrent_load` | LOW / MEDIUM / HIGH | Based on concurrent_users |
| `budget_pressure` | LOW / MEDIUM / HIGH | Direct from budget_level |

## DetectedProblem

An architectural pressure that the scenario's profile reveals. Each problem carries:

- **problem_id** — one of 12 defined problem types (e.g. `HIGH_STORAGE_GROWTH`, `HIGH_AVAILABILITY_REQUIREMENT`)
- **severity** — CRITICAL > HIGH > MEDIUM > LOW
- **evidence** — the specific field values that triggered detection
- **source_fields** — which scenario fields contributed

## Technique

A storage optimization technique loaded from the YAML knowledge base. Each technique specifies:

- What problems it **solves**
- When it's **applicable** (profile conditions)
- **Benefits** and **disadvantages**
- Implementation **complexity** (LOW / MEDIUM / HIGH)
- Impact levels for storage, performance, cost, scalability
- **Prerequisites** (other techniques that must be present)
- **Conflicts** (techniques that are incompatible)

## Recommendation

A scored, prioritized suggestion to apply a specific technique:

- **alignment_score** (0.0-1.0) — deterministic alignment measure, NOT a probability
- **priority** — REQUIRED / RECOMMENDED / OPTIONAL
- **problems_solved** — which detected problems this addresses
- **rationale** — human-readable explanation
- **evidence** — profile conditions and problems that justify this

## Strategy

Recommendations grouped into 7 coherent workload-domain buckets:

| Bucket | Techniques |
|--------|-----------|
| transactional | partitioning, indexing, sharding, schema_optimization, query_optimization |
| object_storage | object_storage, chunking, lifecycle_management |
| caching | caching |
| analytics | columnar_storage, data_aggregation, parquet_format, materialized_views |
| archival | archiving, tiered_storage, data_pruning |
| security | replication |
| general | compression, deduplication (+ anything unassigned) |
