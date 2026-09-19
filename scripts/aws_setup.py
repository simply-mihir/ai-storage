#!/usr/bin/env python3
"""AWS data layer setup — upload synthetic data, create metadata tables, verify."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("aws_setup")

PARQUET_PATH = "data/synthetic/scenarios.parquet"


def main() -> int:
    from storage_advisor.domain.scenario import Scenario
    from storage_advisor.estimation.impact_estimator import estimate_impact
    from storage_advisor.integrations.aws import MetadataStore, S3Store
    from storage_advisor.recommendation.recommendation_engine import (
        run_recommendation_engine,
    )

    # ---- Step 1: Upload Parquet to S3 ----
    logger.info("Step 1: Uploading scenarios.parquet to S3...")
    s3 = S3Store()
    if s3.available:
        uri = s3.upload_parquet(PARQUET_PATH)
        if uri:
            logger.info("Upload complete: %s", uri)
        else:
            logger.error("Upload failed.")
            return 1
    else:
        logger.warning("S3 unavailable — skipping upload.")

    # ---- Step 2: Verify upload ----
    if s3.available:
        logger.info("Step 2: Verifying upload...")
        try:
            import boto3
            import pandas as pd

            client = boto3.client("s3")
            s3_key = f"{s3.prefix}synthetic/scenarios.parquet"
            local_verify = "/tmp/verify_scenarios.parquet"
            client.download_file(s3.bucket_name, s3_key, local_verify)
            df = pd.read_parquet(local_verify)
            logger.info("Verified: %d rows, %d columns", len(df), len(df.columns))
            Path(local_verify).unlink(missing_ok=True)
        except Exception as e:
            logger.error("Verification failed: %s", e)
            return 1
    else:
        logger.warning("Step 2: Skipped (S3 unavailable).")

    # ---- Step 3: Create metadata tables ----
    logger.info("Step 3: Creating metadata tables...")
    meta = MetadataStore()
    logger.info("Backend: %s", meta.backend)

    # ---- Step 4: Insert demo scenario as test run ----
    logger.info("Step 4: Inserting demo scenario run...")
    demo = Scenario(
        business_domain="AI",
        company_size="ENTERPRISE",
        expected_users=10_000_000,
        concurrent_users=100_000,
        current_storage_gb=25_000,
        daily_growth_gb=300,
        data_types=["IMAGES", "DOCUMENTS", "TRANSACTIONS", "LOGS"],
        structured_data_pct=20,
        semi_structured_data_pct=20,
        unstructured_data_pct=60,
        read_intensity="HIGH",
        write_intensity="HIGH",
        access_pattern="MIXED",
        latency_requirement_ms=100,
        availability_requirement=99.99,
        rto_minutes=60,
        rpo_minutes=15,
        retention_years=7,
        budget_level="HIGH",
        analytics_required=True,
        real_time_processing_required=True,
        sensitive_data=True,
        encryption_required=True,
        compliance_requirements=["NONE"],
    )
    result = run_recommendation_engine(demo)
    impact = estimate_impact(demo, result.recommendations)
    run_id = meta.save_run(demo, result, impact)
    logger.info("Saved run: %s", run_id)

    # ---- Step 5: Verify metadata ----
    logger.info("Step 5: Verifying metadata...")
    runs = meta.recent_runs()
    for run in runs:
        logger.info(
            "  Run %s: domain=%s, recs=%s, storage=%.1f%%, cost=%.1f%%",
            run["id"][:8],
            run["domain"],
            run["recommendation_count"],
            run["storage_reduction_pct"],
            run["cost_reduction_pct"],
        )

    stats = meta.domain_stats()
    logger.info("Domain stats: %s", stats)

    logger.info("AWS data layer ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
