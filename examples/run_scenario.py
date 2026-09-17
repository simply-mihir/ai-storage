#!/usr/bin/env python3
"""CLI demo — run one or all sample scenarios through the recommendation engine.

Usage:
    python examples/run_scenario.py                    # run all scenarios
    python examples/run_scenario.py --scenario 0       # run first scenario
    python examples/run_scenario.py --json             # output raw JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.recommendation.recommendation_engine import run_recommendation_engine


SCENARIOS_FILE = Path(__file__).parent / "sample_scenarios.json"


def load_sample_scenarios() -> list[dict]:
    data = json.loads(SCENARIOS_FILE.read_text())
    return data["scenarios"]


def print_report(name: str, scenario: Scenario, result, impact) -> None:
    width = 70
    print("=" * width)
    print(f"  SCENARIO: {name}")
    print("=" * width)
    print()

    print(f"  Domain: {scenario.business_domain}  |  Size: {scenario.company_size}")
    print(f"  Users: {scenario.expected_users:,}  |  Concurrent: {scenario.concurrent_users:,}")
    print(f"  Storage: {scenario.current_storage_gb:,.0f} GB  |  Growth: {scenario.daily_growth_gb:,.0f} GB/day")
    print(f"  Latency: {scenario.latency_requirement_ms} ms  |  Availability: {scenario.availability_requirement}%")
    print(f"  Retention: {scenario.retention_years} years  |  Budget: {scenario.budget_level}")
    print()

    print(f"  DETECTED PROBLEMS ({len(result.detected_problems)}):")
    for p in result.detected_problems:
        print(f"    [{p['severity']:8s}] {p['problem_id']}")
    print()

    print(f"  RECOMMENDATIONS ({len(result.recommendations)}):")
    for r in result.recommendations:
        print(f"    [{r.priority:11s}] {r.technique_name:25s}  score={r.alignment_score:.3f}")
        print(f"                  solves: {', '.join(r.problems_solved)}")
    print()

    print("  STRATEGY:")
    for bucket in ["transactional", "object_storage", "caching", "analytics", "archival", "security", "general"]:
        items = getattr(result.strategy, bucket)
        if items:
            print(f"    {bucket.upper()}:")
            for r in items:
                print(f"      -> {r.technique_name} ({r.priority})")
    print()

    print("  IMPACT ESTIMATES [MODEL-BASED]:")
    print(f"    Storage: {impact.storage.current_storage_gb:,.0f} GB -> {impact.storage.projected_storage_gb:,.0f} GB ({impact.storage.estimated_reduction_pct}% reduction)")
    print(f"    Cost:    ${impact.cost.estimated_monthly_baseline_usd:,.2f} -> ${impact.cost.estimated_monthly_optimized_usd:,.2f}/month ({impact.cost.estimated_savings_pct}% savings)")
    print(f"    Latency: {impact.latency.current_effective_latency_ms} ms -> {impact.latency.estimated_optimized_latency_ms} ms ({impact.latency.estimated_improvement_pct}% improvement)")
    print()
    print("-" * width)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Data Architect - Demo")
    parser.add_argument("--scenario", type=int, help="Run specific scenario by index (0-based)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted report")
    args = parser.parse_args()

    samples = load_sample_scenarios()

    if args.scenario is not None:
        if args.scenario < 0 or args.scenario >= len(samples):
            print(f"Error: scenario index must be 0-{len(samples)-1}")
            sys.exit(1)
        samples = [samples[args.scenario]]

    for entry in samples:
        name = entry["name"]
        scenario = Scenario(**entry["scenario"])
        result = run_recommendation_engine(scenario)
        impact = estimate_impact(scenario, result.recommendations)

        if args.json:
            output = {
                "scenario_name": name,
                "result": json.loads(result.model_dump_json()),
                "impact": json.loads(impact.model_dump_json()),
            }
            print(json.dumps(output, indent=2))
        else:
            print_report(name, scenario, result, impact)


if __name__ == "__main__":
    main()
