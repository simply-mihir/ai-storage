"""Synthetic scenario generator — produces a Parquet dataset by running
domain-specific priors through the full recommendation pipeline.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path

import numpy as np
import pandas as pd

from storage_advisor.architecture.builder import ArchitectureBuilder
from storage_advisor.detection.problem_detector import detect_problems
from storage_advisor.domain.problems import ProblemId
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.profiling.workload_profiler import profile_workload
from storage_advisor.recommendation.recommendation_engine import (
    run_recommendation_engine,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain prior definitions
# ---------------------------------------------------------------------------

_DOMAIN_DATA_TYPES = {
    "fintech":    (["TRANSACTIONS", "LOGS"], [40, 30, 30]),
    "healthcare": (["DOCUMENTS", "IMAGES", "TEXT"], [30, 40, 30]),
    "media":      (["VIDEOS", "IMAGES", "AUDIO"], [10, 30, 60]),
    "gaming":     (["LOGS", "TIME_SERIES", "CLICKSTREAM"], [40, 30, 30]),
    "saas":       (["TEXT", "DOCUMENTS", "TRANSACTIONS"], [40, 30, 30]),
    "iot":        (["SENSOR_DATA", "TIME_SERIES", "LOGS"], [10, 30, 60]),
    "ai_startup": (["EMBEDDINGS", "ML_FEATURES", "IMAGES"], [20, 30, 50]),
    "ecommerce":  (["TRANSACTIONS", "IMAGES", "CLICKSTREAM"], [30, 30, 40]),
}

_DOMAIN_COMPANY_SIZES = {
    "fintech":    (["STARTUP", "MEDIUM", "LARGE", "ENTERPRISE"], [2, 3, 3, 2]),
    "healthcare": (["MEDIUM", "LARGE", "ENTERPRISE"], [3, 4, 3]),
    "media":      (["STARTUP", "MEDIUM", "LARGE", "ENTERPRISE"], [1, 2, 3, 4]),
    "gaming":     (["STARTUP", "MEDIUM", "LARGE"], [3, 4, 3]),
    "saas":       (["STARTUP", "SMALL", "MEDIUM", "LARGE"], [3, 3, 3, 1]),
    "iot":        (["STARTUP", "MEDIUM", "LARGE", "ENTERPRISE"], [1, 3, 3, 3]),
    "ai_startup": (["STARTUP", "SMALL", "MEDIUM"], [5, 3, 2]),
    "ecommerce":  (["SMALL", "MEDIUM", "LARGE", "ENTERPRISE"], [2, 3, 3, 2]),
}

_DOMAIN_ACCESS_PATTERNS = {
    "fintech":    (["RANDOM", "MIXED"], [3, 7]),
    "healthcare": (["SEQUENTIAL", "MIXED"], [4, 6]),
    "media":      (["SEQUENTIAL", "MIXED"], [6, 4]),
    "gaming":     (["RANDOM", "MIXED"], [5, 5]),
    "saas":       (["RANDOM", "MIXED", "SEQUENTIAL"], [3, 5, 2]),
    "iot":        (["SEQUENTIAL", "MIXED"], [7, 3]),
    "ai_startup": (["RANDOM", "MIXED", "SEQUENTIAL"], [3, 4, 3]),
    "ecommerce":  (["RANDOM", "MIXED"], [6, 4]),
}


def _weighted_choice(rng: random.Random, options: list, weights: list):
    return rng.choices(options, weights=weights, k=1)[0]


def _log_uniform(rng: random.Random, low: float, high: float) -> float:
    log_low, log_high = np.log(low), np.log(high)
    return float(np.exp(rng.uniform(log_low, log_high)))


_DOMAIN_PRIORS = {
    "fintech": {
        "users": (10_000, 5_000_000),
        "daily_growth_gb": (1, 200),
        "read_intensity": (["HIGH", "MEDIUM", "LOW"], [3, 2, 1]),
        "write_intensity": (["MEDIUM", "HIGH"], [3, 2]),
        "latency_ms": [10, 50, 100],
        "availability_pct": [99.99, 99.999],
        "compliance": ([["PCI_DSS"], ["PCI_DSS", "SOC2"], ["SOC2"]], [1, 1, 1]),
        "retention_years": [5, 7, 10],
        "analytics": ([True, False], [2, 1]),
    },
    "healthcare": {
        "users": (1_000, 500_000),
        "daily_growth_gb": (5, 500),
        "read_intensity": (["MEDIUM", "HIGH", "LOW"], [3, 2, 1]),
        "write_intensity": (["LOW", "MEDIUM"], [2, 3]),
        "latency_ms": [100, 200, 500],
        "availability_pct": [99.9, 99.99],
        "compliance": ([["HIPAA"]], [1]),
        "retention_years": [7, 10, 15],
        "analytics": ([True, False], [3, 1]),
    },
    "media": {
        "users": (100_000, 50_000_000),
        "daily_growth_gb": (100, 5000),
        "read_intensity": (["HIGH"], [1]),
        "write_intensity": (["LOW", "MEDIUM", "HIGH"], [2, 2, 1]),
        "latency_ms": [50, 100, 200],
        "availability_pct": [99.9, 99.99],
        "compliance": ([["NONE"], ["GDPR"]], [4, 2]),
        "retention_years": [1, 3, 5],
        "analytics": ([True, False], [3, 1]),
    },
    "gaming": {
        "users": (50_000, 20_000_000),
        "daily_growth_gb": (10, 1000),
        "read_intensity": (["HIGH"], [1]),
        "write_intensity": (["HIGH", "MEDIUM"], [3, 2]),
        "latency_ms": [10, 20, 50],
        "availability_pct": [99.99, 99.999],
        "compliance": ([["NONE"]], [1]),
        "retention_years": [1, 2, 3],
        "analytics": ([True, False], [2, 1]),
    },
    "saas": {
        "users": (1_000, 2_000_000),
        "daily_growth_gb": (1, 300),
        "read_intensity": (["HIGH", "MEDIUM", "LOW"], [2, 3, 1]),
        "write_intensity": (["MEDIUM", "HIGH", "LOW"], [3, 1, 2]),
        "latency_ms": [50, 100, 200],
        "availability_pct": [99.9, 99.99],
        "compliance": ([["NONE"], ["SOC2"], ["GDPR"]], [3, 2, 1]),
        "retention_years": [1, 3, 5, 7],
        "analytics": ([True, False], [2, 1]),
    },
    "iot": {
        "users": (10_000, 10_000_000),
        "daily_growth_gb": (50, 10000),
        "read_intensity": (["LOW", "MEDIUM"], [2, 3]),
        "write_intensity": (["HIGH"], [1]),
        "latency_ms": [100, 500, 1000],
        "availability_pct": [99.9, 99.99],
        "compliance": ([["NONE"], ["SOC2"]], [3, 1]),
        "retention_years": [1, 3, 5],
        "analytics": ([True, False], [4, 1]),
    },
    "ai_startup": {
        "users": (5_000, 10_000_000),
        "daily_growth_gb": (50, 2000),
        "read_intensity": (["HIGH", "MEDIUM"], [3, 2]),
        "write_intensity": (["HIGH", "MEDIUM"], [2, 3]),
        "latency_ms": [50, 100, 200],
        "availability_pct": [99.9, 99.99],
        "compliance": ([["NONE"], ["GDPR"], ["SOC2"]], [3, 1, 1]),
        "retention_years": [3, 5, 7],
        "analytics": ([True], [1]),
    },
    "ecommerce": {
        "users": (10_000, 5_000_000),
        "daily_growth_gb": (10, 500),
        "read_intensity": (["HIGH"], [1]),
        "write_intensity": (["MEDIUM", "HIGH"], [3, 2]),
        "latency_ms": [50, 100, 200],
        "availability_pct": [99.9, 99.99],
        "compliance": ([["PCI_DSS"], ["PCI_DSS", "GDPR"], ["NONE"]], [3, 1, 1]),
        "retention_years": [3, 5, 7],
        "analytics": ([True, False], [3, 1]),
    },
}

_DOMAIN_BACKUP_FREQ = {
    "fintech":    [14, 21, 28, 42],
    "healthcare": [14, 21, 28],
    "media":      [1, 3, 7],
    "gaming":     [3, 7, 14],
    "saas":       [7, 14, 21],
    "iot":        [1, 3, 7],
    "ai_startup": [3, 7, 14],
    "ecommerce":  [7, 14, 21],
}

_DOMAIN_ML_PROB = {
    "fintech": 0.10, "healthcare": 0.20, "media": 0.20, "gaming": 0.30,
    "saas": 0.15, "iot": 0.30, "ai_startup": 0.80, "ecommerce": 0.25,
}

_DOMAIN_STREAMING_PROB = {
    "fintech": 0.30, "healthcare": 0.10, "media": 0.60, "gaming": 0.40,
    "saas": 0.15, "iot": 0.70, "ai_startup": 0.40, "ecommerce": 0.30,
}

_BUSINESS_DOMAIN_MAP = {
    "fintech": "FINTECH",
    "healthcare": "HEALTHCARE",
    "media": "MEDIA",
    "gaming": "GAMING",
    "saas": "SAAS",
    "iot": "IOT",
    "ai_startup": "AI",
    "ecommerce": "ECOMMERCE",
}

_BUDGET_BY_COMPANY = {
    "STARTUP": (["LOW", "MEDIUM"], [3, 2]),
    "SMALL": (["LOW", "MEDIUM"], [2, 3]),
    "MEDIUM": (["MEDIUM", "HIGH"], [3, 2]),
    "LARGE": (["MEDIUM", "HIGH"], [2, 3]),
    "ENTERPRISE": (["HIGH", "MEDIUM"], [4, 1]),
}


def _sample_scenario(
    rng: random.Random, domain: str, scenario_id: str,
) -> dict:
    priors = _DOMAIN_PRIORS[domain]

    users = int(_log_uniform(rng, *priors["users"]))
    concurrent_pct = rng.uniform(0.02, 0.15)
    concurrent_users = max(1, int(users * concurrent_pct))

    daily_growth = round(rng.uniform(*priors["daily_growth_gb"]), 1)
    storage_gb = round(daily_growth * rng.uniform(30, 365), 1)
    storage_gb = max(storage_gb, 10.0)

    read_int = _weighted_choice(rng, *priors["read_intensity"])
    write_int = _weighted_choice(rng, *priors["write_intensity"])
    latency_ms = rng.choice(priors["latency_ms"])
    availability_pct = rng.choice(priors["availability_pct"])
    compliance = _weighted_choice(rng, *priors["compliance"])
    retention_years = rng.choice(priors["retention_years"])
    analytics = _weighted_choice(rng, *priors["analytics"])

    dt_opts, dt_weights = _DOMAIN_DATA_TYPES[domain]
    struct_pct = float(dt_weights[0])
    semi_pct = float(dt_weights[1])
    unstruct_pct = float(dt_weights[2])
    noise = rng.uniform(-10, 10)
    struct_pct = max(5, min(90, struct_pct + noise))
    semi_pct = max(5, min(90, semi_pct - noise * 0.5))
    unstruct_pct = 100.0 - struct_pct - semi_pct
    unstruct_pct = max(0, unstruct_pct)
    total = struct_pct + semi_pct + unstruct_pct
    struct_pct = round(struct_pct / total * 100, 1)
    semi_pct = round(semi_pct / total * 100, 1)
    unstruct_pct = round(100.0 - struct_pct - semi_pct, 1)

    company_size = _weighted_choice(rng, *_DOMAIN_COMPANY_SIZES[domain])
    budget = _weighted_choice(rng, *_BUDGET_BY_COMPANY[company_size])
    access_pattern = _weighted_choice(rng, *_DOMAIN_ACCESS_PATTERNS[domain])

    rto_minutes = rng.choice([10, 30, 60, 120, 240, 480])
    rpo_minutes = rng.choice([5, 15, 30, 60, 120, 240])
    rpo_minutes = min(rpo_minutes, rto_minutes)

    has_compliance = compliance != ["NONE"]
    sensitive = has_compliance or rng.random() < 0.3
    encryption = sensitive or rng.random() < 0.2
    real_time = (latency_ms <= 50 and write_int == "HIGH") or rng.random() < 0.3

    rto_hours = rto_minutes / 60.0
    rpo_hours = rpo_minutes / 60.0
    backup_freq = rng.choice(_DOMAIN_BACKUP_FREQ[domain])
    realtime_req = latency_ms <= 20 or (latency_ms <= 50 and rng.random() < 0.4)
    ml_req = rng.random() < _DOMAIN_ML_PROB[domain]
    streaming_req = rng.random() < _DOMAIN_STREAMING_PROB[domain]

    return {
        "scenario_id": scenario_id,
        "domain": domain,
        "schema_version": 2,
        "business_domain": _BUSINESS_DOMAIN_MAP[domain],
        "company_size": company_size,
        "expected_users": users,
        "concurrent_users": concurrent_users,
        "current_storage_gb": storage_gb,
        "daily_growth_gb": daily_growth,
        "data_types": dt_opts,
        "structured_data_pct": struct_pct,
        "semi_structured_data_pct": semi_pct,
        "unstructured_data_pct": unstruct_pct,
        "read_intensity": read_int,
        "write_intensity": write_int,
        "access_pattern": access_pattern,
        "latency_requirement_ms": float(latency_ms),
        "availability_requirement": availability_pct,
        "rto_minutes": float(rto_minutes),
        "rpo_minutes": float(rpo_minutes),
        "retention_years": float(retention_years),
        "budget_level": budget,
        "analytics_required": analytics,
        "real_time_processing_required": real_time,
        "sensitive_data": sensitive,
        "encryption_required": encryption,
        "compliance_requirements": compliance,
        "rto_hours": rto_hours,
        "rpo_hours": rpo_hours,
        "backup_frequency_per_week": backup_freq,
        "realtime_required": realtime_req,
        "ml_required": ml_req,
        "streaming_required": streaming_req,
    }


# ---------------------------------------------------------------------------
# ScenarioGenerator
# ---------------------------------------------------------------------------

class ScenarioGenerator:

    def generate(
        self,
        n: int = 2000,
        seed: int = 42,
        output_dir: str = "data/synthetic/",
    ) -> str:
        random.seed(seed)
        np.random.seed(seed)
        rng = random.Random(seed)

        techniques = load_techniques()
        builder = ArchitectureBuilder()

        domains = list(_DOMAIN_PRIORS.keys())
        per_domain = n // len(domains)
        remainder = n % len(domains)

        assignments: list[str] = []
        for i, d in enumerate(domains):
            count = per_domain + (1 if i < remainder else 0)
            assignments.extend([d] * count)
        rng.shuffle(assignments)

        rows: list[dict] = []
        failures: list[str] = []

        for i, domain in enumerate(assignments):
            scenario_id = f"{domain}_{i:04d}"
            try:
                raw = _sample_scenario(rng, domain, scenario_id)
                scenario = Scenario(**{
                    k: v for k, v in raw.items()
                    if k not in ("scenario_id", "domain")
                })

                profile = profile_workload(scenario)
                problems = detect_problems(scenario, profile)
                result = run_recommendation_engine(scenario, techniques)
                impact = estimate_impact(scenario, result.recommendations)
                arch = builder.build(scenario, result)

                problem_ids = [p.problem_id for p in problems]
                all_rec_ids = [r.technique_id for r in result.recommendations]
                required_ids = [
                    r.technique_id for r in result.recommendations
                    if r.priority == "REQUIRED"
                ]
                top_technique = all_rec_ids[0] if all_rec_ids else ""
                rec_id_set = set(all_rec_ids)

                row = {
                    "scenario_id": raw["scenario_id"],
                    "domain": raw["domain"],
                    "users": raw["expected_users"],
                    "concurrent_users": raw["concurrent_users"],
                    "storage_size_gb": raw["current_storage_gb"],
                    "daily_growth_gb": raw["daily_growth_gb"],
                    "data_types": json.dumps(raw["data_types"]),
                    "read_intensity": raw["read_intensity"],
                    "write_intensity": raw["write_intensity"],
                    "latency_ms": raw["latency_requirement_ms"],
                    "availability_pct": raw["availability_requirement"],
                    "rto_hours": raw["rto_hours"],
                    "rpo_hours": raw["rpo_hours"],
                    "retention_years": raw["retention_years"],
                    "compliance": json.dumps(raw["compliance_requirements"]),
                    "analytics_flag": raw["analytics_required"],
                    "budget_tier": raw["budget_level"],
                    "backup_frequency_per_week": raw["backup_frequency_per_week"],
                    "realtime_required": raw["realtime_required"],
                    "ml_required": raw["ml_required"],
                    "streaming_required": raw["streaming_required"],
                    # Profiler
                    "profile_read_category": str(profile.read_pressure),
                    "profile_write_category": str(profile.write_pressure),
                    "profile_growth_category": str(profile.storage_growth),
                    "profile_scale_category": str(profile.scalability_pressure),
                    # Problems
                    "detected_problems": json.dumps(problem_ids),
                    "problem_count": len(problem_ids),
                    "has_high_availability_req": ProblemId.HIGH_AVAILABILITY_REQUIREMENT in problem_ids,
                    "has_high_growth": (
                        ProblemId.HIGH_STORAGE_GROWTH in problem_ids
                        or ProblemId.EXTREME_STORAGE_GROWTH in problem_ids
                    ),
                    "has_cost_pressure": raw["budget_level"] == "LOW",
                    # Recommendations
                    "all_technique_ids": json.dumps(all_rec_ids),
                    "required_technique_ids": json.dumps(required_ids),
                    "recommendation_count": len(all_rec_ids),
                    "top_technique": top_technique,
                    "has_caching": "caching" in rec_id_set,
                    "has_partitioning": "partitioning" in rec_id_set,
                    "has_sharding": "sharding" in rec_id_set,
                    "has_tiered_storage": "tiered_storage" in rec_id_set,
                    "has_object_storage": "object_storage" in rec_id_set,
                    "has_columnar": "columnar_storage" in rec_id_set,
                    # Impact
                    "baseline_storage_gb": impact.storage.current_storage_gb,
                    "optimized_storage_gb": impact.storage.projected_storage_gb,
                    "storage_reduction_pct": impact.storage.estimated_reduction_pct,
                    "baseline_cost_usd": impact.cost.estimated_monthly_baseline_usd,
                    "optimized_cost_usd": impact.cost.estimated_monthly_optimized_usd,
                    "cost_reduction_pct": impact.cost.estimated_savings_pct,
                    "baseline_latency_ms": impact.latency.current_effective_latency_ms,
                    "optimized_latency_ms": impact.latency.estimated_optimized_latency_ms,
                    "latency_improvement_pct": impact.latency.estimated_improvement_pct,
                    # Architecture
                    "architecture_services": json.dumps(
                        [c.service for c in arch.components]
                    ),
                    "component_count": len(arch.components),
                }
                rows.append(row)

            except (ValueError, KeyError, TypeError) as e:
                failures.append(f"{scenario_id}: {e}")
                logger.warning("Scenario %s failed: %s", scenario_id, e)

            if (i + 1) % 200 == 0:
                print(f"  Progress: {i + 1}/{n} scenarios generated")

        df = pd.DataFrame(rows)

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        parquet_path = out / "scenarios.parquet"
        csv_path = out / "scenarios.csv"

        df.to_parquet(parquet_path, engine="pyarrow", index=False)
        df.to_csv(csv_path, index=False)

        # --- Summary ---
        print(f"\n{'=' * 60}")
        print(f"Generated: {len(rows)} scenarios")
        print(f"Failed:    {len(failures)}")
        if failures:
            for f in failures[:10]:
                print(f"  - {f}")
            if len(failures) > 10:
                print(f"  ... and {len(failures) - 10} more")

        print(f"\nSchema ({len(df.columns)} columns):")
        for col in df.columns:
            print(f"  {col:<35} {df[col].dtype}")

        print("\nFirst 3 rows:")
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(df.head(3).to_string(index=False))

        for metric in ["storage_reduction_pct", "cost_reduction_pct"]:
            col = df[metric]
            print(
                f"\n{metric}:  mean={col.mean():.1f}  median={col.median():.1f}"
                f"  min={col.min():.1f}  max={col.max():.1f}"
            )

        print("\nScenarios per domain:")
        for domain, count in df["domain"].value_counts().sort_index().items():
            print(f"  {domain:<15} {count}")

        print(f"\nOutput: {parquet_path.resolve()}")
        return str(parquet_path)
