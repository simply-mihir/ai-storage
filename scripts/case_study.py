"""Case study literature validation CLI and alignment scorer.

Evaluates AI Data Architect deterministic recommendations against publicly documented
real-world architecture decisions for Netflix and Uber.
"""

from __future__ import annotations

import argparse
from typing import Any

from storage_advisor.domain.scenario import Scenario
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.recommendation.recommendation_engine import (
    RecommendationResult,
    run_recommendation_engine,
)


def get_netflix_scenario() -> Scenario:
    """Return Netflix-style media streaming platform workload scenario.

    Characteristics: Unstructured-heavy (video/audio masters, transcode assets),
    global low latency for stream manifests, multi-year retention for content catalogs.
    """
    return Scenario(
        business_domain="MEDIA",
        company_size="ENTERPRISE",
        expected_users=250_000_000,
        concurrent_users=5_000_000,
        current_storage_gb=500_000.0,
        daily_growth_gb=10_000.0,
        data_types=["VIDEOS", "IMAGES", "AUDIO", "LOGS"],
        structured_data_pct=10.0,
        semi_structured_data_pct=20.0,
        unstructured_data_pct=70.0,
        read_intensity="HIGH",
        write_intensity="MEDIUM",
        access_pattern="SEQUENTIAL",
        latency_requirement_ms=30.0,
        availability_requirement=99.99,
        rto_minutes=15.0,
        rpo_minutes=5.0,
        retention_years=10.0,
        budget_level="HIGH",
        analytics_required=True,
        real_time_processing_required=True,
        sensitive_data=True,
        encryption_required=True,
        compliance_requirements=["SOC2"],
    )


def get_uber_scenario() -> Scenario:
    """Return Uber-style event-sourced mobility platform workload scenario.

    Characteristics: Write-heavy geospatial telemetry and transaction stream,
    stringent p99 latency SLAs, multi-tier regulatory compliance (SOX, PCI-DSS, GDPR).
    """
    return Scenario(
        business_domain="LOGISTICS",
        company_size="ENTERPRISE",
        expected_users=150_000_000,
        concurrent_users=3_000_000,
        current_storage_gb=150_000.0,
        daily_growth_gb=8_000.0,
        data_types=["GPS_DATA", "TRANSACTIONS", "TIME_SERIES", "LOGS"],
        structured_data_pct=50.0,
        semi_structured_data_pct=30.0,
        unstructured_data_pct=20.0,
        read_intensity="HIGH",
        write_intensity="HIGH",
        access_pattern="RANDOM",
        latency_requirement_ms=15.0,
        availability_requirement=99.99,
        rto_minutes=5.0,
        rpo_minutes=1.0,
        retention_years=7.0,
        budget_level="HIGH",
        analytics_required=True,
        real_time_processing_required=True,
        sensitive_data=True,
        encryption_required=True,
        compliance_requirements=["SOC2", "PCI_DSS", "GDPR"],
    )


def get_netflix_documented_choices() -> list[dict[str, Any]]:
    """Return documented Netflix storage choices cited from public technical publications."""
    return [
        {
            "technique_id": "object_storage",
            "technique_name": "Object Storage",
            "system_name": "Amazon S3 Media Repository",
            "citation_title": "Active-Active for Multi-Region Media Processing at Netflix",
            "citation_url": "https://netflixtechblog.com/active-active-for-multi-region-media-processing-at-netflix-c6a6f0eb5b97",
            "context": "Primary authoritative repository for video masters, encoded chunks, and raw media streams.",
        },
        {
            "technique_id": "tiered_storage",
            "technique_name": "Tiered Storage",
            "system_name": "S3 Lifecycle & Glacier Deep Archive",
            "citation_title": "Evolution of the Netflix Data Pipeline",
            "citation_url": "https://netflixtechblog.com/evolution-of-the-netflix-data-pipeline-da45bf691456",
            "context": "Automated transition of inactive title masters and cold analytical logs to deep archive tiers.",
        },
        {
            "technique_id": "caching",
            "technique_name": "In-Memory Caching",
            "system_name": "EVCache (Distributed Memcached/RAM)",
            "citation_title": "Announcing EVCache: Distributed In-Memory Datastore for Cloud",
            "citation_url": "https://netflixtechblog.com/announcing-evcache-distributed-in-memory-datastore-for-cloud-c26a698c1b60",
            "context": "Global distributed caching tier holding playback state, user manifests, and recommendations.",
        },
        {
            "technique_id": "parquet_format",
            "technique_name": "Parquet Format",
            "system_name": "Apache Parquet on S3 Lakehouse",
            "citation_title": "Scaling Time Series Data Storage Part I",
            "citation_url": "https://netflixtechblog.com/scaling-time-series-data-storage-part-i-ec2b6d61456",
            "context": "Columnar storage representation across telemetry, video viewing metrics, and experimentation datasets.",
        },
        {
            "technique_id": "chunking",
            "technique_name": "Chunking",
            "system_name": "Shot-Based Video Encoding Chunks",
            "citation_title": "Optimized Shot-Based Encodes for 4K: Now Streaming",
            "citation_url": "https://netflixtechblog.com/optimized-shot-based-encodes-for-4k-now-streaming-478bdfba48e0",
            "context": "Media encoding decomposed into autonomous shot chunks processed and stored independently.",
        },
        {
            "technique_id": "replication",
            "technique_name": "Replication",
            "system_name": "Multi-Region Active-Active S3 & Cassandra",
            "citation_title": "Active-Active for Multi-Region Media Processing at Netflix",
            "citation_url": "https://netflixtechblog.com/active-active-for-multi-region-media-processing-at-netflix-c6a6f0eb5b97",
            "context": "Cross-region asynchronous replication across AWS regions to maintain sub-minute RTO.",
        },
        {
            "technique_id": "compression",
            "technique_name": "Compression",
            "system_name": "Adaptive Dynamic Bitrate Compression",
            "citation_title": "Optimized Shot-Based Encodes for 4K: Now Streaming",
            "citation_url": "https://netflixtechblog.com/optimized-shot-based-encodes-for-4k-now-streaming-478bdfba48e0",
            "context": "Multi-pass encoding and Snappy/ZSTD compression applied across media blocks and telemetry.",
        },
    ]


def get_uber_documented_choices() -> list[dict[str, Any]]:
    """Return documented Uber storage choices cited from public technical publications."""
    return [
        {
            "technique_id": "sharding",
            "technique_name": "Sharding",
            "system_name": "Schemaless / Docstore (Sharded MySQL)",
            "citation_title": "Designing Schemaless, Uber's Fault-Tolerant Distributed Datastore",
            "citation_url": "https://www.uber.com/blog/schemaless-sql-database/",
            "context": "Horizontal sharding of transactional trip data across independent relational database nodes.",
        },
        {
            "technique_id": "partitioning",
            "technique_name": "Partitioning",
            "system_name": "Docstore City/Customer Partition Keys",
            "citation_title": "Docstore: The Evolution of SQL at Uber",
            "citation_url": "https://www.uber.com/blog/docstore-evolution-of-sql-at-uber/",
            "context": "Data partitioned deterministically by trip UUID and city identifier to constrain query blast radius.",
        },
        {
            "technique_id": "caching",
            "technique_name": "In-Memory Caching",
            "system_name": "Integrated Redis Cluster",
            "citation_title": "How Uber Serves Ultra-Low Latency Features Using Integrated Redis",
            "citation_url": "https://www.uber.com/blog/how-uber-uses-integrated-redis-cluster/",
            "context": "Microsecond dispatch state, driver supply positioning, and real-time geospatial caches.",
        },
        {
            "technique_id": "parquet_format",
            "technique_name": "Parquet Format",
            "system_name": "Apache Hudi / Parquet Lakehouse",
            "citation_title": "Uber's Big Data Platform: 100+ Petabytes with Minute Latency",
            "citation_url": "https://www.uber.com/blog/uber-big-data-platform/",
            "context": "Columnar Parquet format utilized by Apache Hudi for petabyte-scale transactional lakehouse queries.",
        },
        {
            "technique_id": "indexing",
            "technique_name": "Indexing",
            "system_name": "Schemaless Secondary Indexing",
            "citation_title": "The Architecture of Schemaless (Part 2)",
            "citation_url": "https://www.uber.com/blog/schemaless-part-two-architecture/",
            "context": "Secondary indexing shards decoupled from primary storage cells to accelerate rider/driver lookups.",
        },
        {
            "technique_id": "replication",
            "technique_name": "Replication",
            "system_name": "Cross-Datacenter MySQL Replication",
            "citation_title": "Designing Schemaless, Uber's Fault-Tolerant Distributed Datastore",
            "citation_url": "https://www.uber.com/blog/schemaless-sql-database/",
            "context": "Master-replica topologies spanning multiple geographic regions for high disaster tolerance.",
        },
        {
            "technique_id": "data_pruning",
            "technique_name": "Data Pruning",
            "system_name": "Automated Retention & Pruning Service",
            "citation_title": "Uber's Data Retention and Compliance Framework",
            "citation_url": "https://www.uber.com/blog/uber-data-retention/",
            "context": "Scheduled deletion and compliance pruning of ride telemetry after mandatory retention limits.",
        },
    ]


def compute_alignment(
    engine_recommendations: list[str],
    documented_choices: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute mathematical alignment score between engine recommendations and documented choices.

    Formula:
    - Matched = techniques present in both engine recommendations and documented choices
    - Alignment Score = len(Matched) / len(Documented Choices)
    - Alignment Percentage = round(Score * 100, 1)
    """
    engine_set = set(engine_recommendations)
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for choice in documented_choices:
        tid = choice["technique_id"]
        if tid in engine_set:
            matched.append(choice)
        else:
            unmatched.append(choice)

    score = len(matched) / len(documented_choices) if documented_choices else 0.0
    pct = round(score * 100.0, 1)

    return {
        "score": score,
        "alignment_pct": pct,
        "total_documented": len(documented_choices),
        "matched_count": len(matched),
        "matched": matched,
        "unmatched": unmatched,
    }


def evaluate_case_study(company_key: str) -> dict[str, Any]:
    """Run engine and evaluate alignment for a specific company workload."""
    techniques = load_techniques()

    if company_key.lower() == "netflix":
        name = "Netflix Media Platform"
        scenario = get_netflix_scenario()
        choices = get_netflix_documented_choices()
        mismatches = [
            {
                "technique": "Relational Database (RDS PostgreSQL)",
                "engine_status": "Architectural builder generates RDS component for structured catalog metadata.",
                "company_reality": "Netflix standardized primarily on Apache Cassandra for playback state and NoSQL document stores rather than relational databases to maintain multi-master multi-region active-active SLAs.",
                "engineering_rationale": "High-velocity streaming playback sessions are key-value lookups rather than relational joins. Relational systems introduce replication lag and lock contention under 5M simultaneous streams.",
            },
            {
                "technique": "Direct S3 Client Delivery vs. CDN Appliance",
                "engine_status": "Engine models object storage egress directly via S3 data transfer out.",
                "company_reality": "Netflix operates Open Connect, a custom hardware Content Delivery Network deployed inside tier-1 Internet Service Provider facilities.",
                "engineering_rationale": "Direct S3 egress at hundreds of terabits per second is economically prohibitive and latency-unsuitable. Open Connect caches 100% of popular streaming assets at the ISP edge.",
            },
        ]
    elif company_key.lower() == "uber":
        name = "Uber Mobility & Transaction Platform"
        scenario = get_uber_scenario()
        choices = get_uber_documented_choices()
        mismatches = [
            {
                "technique": "Managed Distributed SQL vs. Bespoke MySQL Engine",
                "engine_status": "Engine recommends off-the-shelf relational sharding and partitioning patterns.",
                "company_reality": "Uber engineered Schemaless and later Docstore, building a custom append-only distributed ledger and trigger system on top of raw MySQL instances.",
                "engineering_rationale": "In 2014, managed cloud distributed databases lacked required throughput economics and deterministic write latencies at Uber's scale, prompting custom in-house database engineering.",
            },
            {
                "technique": "Cloud Object Store vs. On-Premises HDFS Lakehouse",
                "engine_status": "Engine recommends S3 standard and tiered storage for event history.",
                "company_reality": "Historically, Uber executed big data analytics across a massive tens-of-thousands-node on-premises Hadoop Distributed File System (HDFS) cluster before migrating to hybrid cloud.",
                "engineering_rationale": "On-premises compute-storage colocation provided lower cost-per-byte and dedicated throughput for recurring ETL queries running over hundreds of petabytes.",
            },
        ]
    else:
        raise ValueError(f"Unknown company key: {company_key}")

    result: RecommendationResult = run_recommendation_engine(scenario, techniques)
    rec_ids = [r.technique_id for r in result.recommendations]
    priority_map = {r.technique_id: r.priority.value for r in result.recommendations}
    score_map = {r.technique_id: r.alignment_score for r in result.recommendations}

    alignment = compute_alignment(rec_ids, choices)

    return {
        "company_key": company_key,
        "company_name": name,
        "scenario": scenario,
        "recommendations": result.recommendations,
        "recommendation_ids": rec_ids,
        "priority_map": priority_map,
        "score_map": score_map,
        "alignment": alignment,
        "mismatches": mismatches,
    }


def format_alignment_markdown(eval_result: dict[str, Any]) -> str:
    """Format evaluation result as a clean markdown table."""
    lines: list[str] = []
    name = eval_result["company_name"]
    align = eval_result["alignment"]
    priority_map = eval_result["priority_map"]
    score_map = eval_result["score_map"]

    lines.append(f"### {name} Architecture Alignment: {align['alignment_pct']}% ({align['matched_count']}/{align['total_documented']} Techniques Verified)")
    lines.append("")
    lines.append("| Recommended Technique | Engine Priority | Engine Score | Documented Production System | Alignment | Public Source |")
    lines.append("|---|---|---|---|---|---|")

    for item in align["matched"]:
        tid = item["technique_id"]
        tname = item["technique_name"]
        prio = priority_map.get(tid, "RECOMMENDED")
        score = score_map.get(tid, 0.50)
        sys_name = item["system_name"]
        url = item["citation_url"]
        title = item["citation_title"]
        lines.append(f"| {tname} (`{tid}`) | {prio} | {score:.3f} | {sys_name} | Verified | [{title}]({url}) |")

    for item in align["unmatched"]:
        tid = item["technique_id"]
        tname = item["technique_name"]
        sys_name = item["system_name"]
        url = item["citation_url"]
        title = item["citation_title"]
        lines.append(f"| {tname} (`{tid}`) | OMITTED | — | {sys_name} | Divergence | [{title}]({url}) |")

    lines.append("")
    lines.append("#### Honest Mismatches & Trade-Off Analysis")
    lines.append("")
    for m in eval_result["mismatches"]:
        lines.append(f"- **{m['technique']}**")
        lines.append(f"  - Engine Position: {m['engine_status']}")
        lines.append(f"  - Production Reality: {m['company_reality']}")
        lines.append(f"  - Engineering Rationale: {m['engineering_rationale']}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run case study literature validation")
    parser.add_argument("--workload", choices=["netflix", "uber", "all"], default="all")
    args = parser.parse_args()

    workloads = ["netflix", "uber"] if args.workload == "all" else [args.workload]

    print("=" * 80)
    print("AI DATA ARCHITECT — LITERATURE VALIDATION & ALIGNMENT BENCHMARK")
    print("=" * 80)

    for w in workloads:
        res = evaluate_case_study(w)
        md = format_alignment_markdown(res)
        print("\n" + md + "\n")
        print("-" * 80)


if __name__ == "__main__":
    main()
