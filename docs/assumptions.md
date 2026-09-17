# Assumptions

Every impact estimate in the system is a **model-based projection**, not a measured production value. This document lists every assumption constant, its value, and its rationale.

All constants are defined as named variables in `src/storage_advisor/estimation/impact_estimator.py`.

## Storage Assumptions

| Constant | Value | Meaning |
|----------|-------|---------|
| `ASSUMED_COMPRESSION_RATIO` | 0.45 | Compressed data is 45% of original size (55% savings). Typical for lossless compression on mixed enterprise data. |
| `ASSUMED_DEDUP_RATIO` | 0.20 | 20% of data is duplicate and can be eliminated. Conservative for enterprise environments with backups and versioned data. |
| `ASSUMED_COLUMNAR_COMPRESSION` | 0.30 | Columnar format is 30% of row-oriented size. Applied only to the structured data fraction. |
| `ASSUMED_ARCHIVE_ELIGIBLE_FRACTION` | 0.40 | 40% of data is eligible for archival or pruning over time. Used for both archiving and data pruning estimates. |

## Cost Assumptions

| Constant | Value | Meaning |
|----------|-------|---------|
| `ASSUMED_HOT_TIER_COST_PER_GB` | $0.023/GB/month | S3 Standard pricing. Used as the baseline for all storage cost calculations. |
| `ASSUMED_COLD_TIER_COST_PER_GB` | $0.004/GB/month | S3 Glacier pricing. Applied when tiered_storage or archiving is recommended. |
| `ASSUMED_COLD_DATA_FRACTION` | 0.60 | 60% of retained data becomes cold over time. Determines the split between hot and cold tier pricing. |

## Latency Assumptions

| Constant | Value | Meaning |
|----------|-------|---------|
| `ASSUMED_CACHE_HIT_RATE` | 0.80 | 80% of reads served from cache. Conservative for a well-configured caching layer (Redis, Memcached). |
| `ASSUMED_CACHE_LATENCY_MS` | 2.0 ms | Response time for cache hits. Typical for in-memory cache. |
| `ASSUMED_DB_LATENCY_MS` | 50.0 ms | Baseline database response time (defined but not directly used in current estimates — the scenario's own latency_requirement_ms is used instead). |
| `ASSUMED_PARTITION_SPEEDUP` | 0.40 | Partition-aligned queries run at 40% of original time (60% improvement). |
| `ASSUMED_INDEX_SPEEDUP` | 0.10 | Indexed lookups run at 10% of full-scan time (90% improvement). |

## How Estimates Compound

Storage reduction factors are **multiplicative**. If compression (0.45) and deduplication (0.80 = 1 - 0.20) are both recommended:

```
effective_storage = original × 0.45 × 0.80 = original × 0.36
```

This means 64% total reduction, not 55% + 20% = 75%.

## Limitations

- **No workload-specific tuning** — the same compression ratio is used regardless of data type. Real compression ratios vary widely (text compresses better than images).
- **No implementation cost** — estimates show operational savings but not the engineering effort to implement each technique.
- **Static ratios** — in practice, deduplication ratios depend on data redundancy patterns, cache hit rates depend on access patterns, and compression ratios depend on data entropy.
- **Directional, not prescriptive** — these estimates indicate relative magnitude and direction. They are not suitable for capacity planning or budget forecasting without validation against actual workload measurements.

## System Assumptions

Beyond impact estimates, the recommendation engine makes these assumptions (listed in every `RecommendationResult`):

1. All impact estimates are model-based, not measured production values
2. Compression ratios assume general-purpose lossless compression
3. Cache hit rates are assumed, not measured
4. Cost impacts are relative directional estimates, not exact dollar amounts
5. Technique applicability is based on workload profile classification thresholds
