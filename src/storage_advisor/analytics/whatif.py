"""What-if analyzer — compares two scenarios through the full pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from storage_advisor.architecture.builder import ArchitectureBuilder, ArchitectureOutput
from storage_advisor.domain.recommendations import RecommendationResult
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import ImpactReport, estimate_impact
from storage_advisor.recommendation.recommendation_engine import (
    run_recommendation_engine,
)


@dataclass
class WhatIfResult:
    baseline: RecommendationResult
    modified: RecommendationResult
    baseline_impact: ImpactReport
    modified_impact: ImpactReport
    baseline_architecture: ArchitectureOutput
    modified_architecture: ArchitectureOutput
    added_techniques: list[str]
    removed_techniques: list[str]
    changed_priorities: list[dict]
    storage_delta_pct: float
    cost_delta_pct: float
    latency_delta_pct: float
    summary: str


class WhatIfAnalyzer:

    def compare(
        self,
        baseline_scenario: Scenario,
        modified_scenario: Scenario,
        engine: Callable[..., RecommendationResult] = run_recommendation_engine,
        estimator: Callable[..., ImpactReport] = estimate_impact,
        builder: ArchitectureBuilder | None = None,
    ) -> WhatIfResult:
        if builder is None:
            builder = ArchitectureBuilder()

        baseline = engine(baseline_scenario)
        modified = engine(modified_scenario)

        baseline_impact = estimator(baseline_scenario, baseline.recommendations)
        modified_impact = estimator(modified_scenario, modified.recommendations)

        baseline_arch = builder.build(baseline_scenario, baseline)
        modified_arch = builder.build(modified_scenario, modified)

        baseline_ids = {r.technique_id for r in baseline.recommendations}
        modified_ids = {r.technique_id for r in modified.recommendations}

        added = sorted(modified_ids - baseline_ids)
        removed = sorted(baseline_ids - modified_ids)

        baseline_priorities = {
            r.technique_id: r.priority for r in baseline.recommendations
        }
        modified_priorities = {
            r.technique_id: r.priority for r in modified.recommendations
        }
        changed = []
        for tid in baseline_ids & modified_ids:
            old_p = baseline_priorities[tid]
            new_p = modified_priorities[tid]
            if old_p != new_p:
                changed.append({
                    "technique_id": tid,
                    "old_priority": old_p,
                    "new_priority": new_p,
                })

        storage_delta = (
            modified_impact.storage.estimated_reduction_pct
            - baseline_impact.storage.estimated_reduction_pct
        )
        cost_delta = (
            modified_impact.cost.estimated_savings_pct
            - baseline_impact.cost.estimated_savings_pct
        )
        latency_delta = (
            modified_impact.latency.estimated_improvement_pct
            - baseline_impact.latency.estimated_improvement_pct
        )

        summary = self._build_summary(
            added, removed, changed, storage_delta,
        )

        return WhatIfResult(
            baseline=baseline,
            modified=modified,
            baseline_impact=baseline_impact,
            modified_impact=modified_impact,
            baseline_architecture=baseline_arch,
            modified_architecture=modified_arch,
            added_techniques=added,
            removed_techniques=removed,
            changed_priorities=changed,
            storage_delta_pct=round(storage_delta, 2),
            cost_delta_pct=round(cost_delta, 2),
            latency_delta_pct=round(latency_delta, 2),
            summary=summary,
        )

    @staticmethod
    def _build_summary(
        added: list[str],
        removed: list[str],
        changed: list[dict],
        storage_delta: float,
    ) -> str:
        if added:
            readable = added[0].replace("_", " ")
            return (
                f"Modified scenario introduces {readable} "
                f"(+{len(added)} technique{'s' if len(added) > 1 else ''} added)."
            )
        if changed:
            ch = changed[0]
            readable = ch["technique_id"].replace("_", " ")
            return (
                f"{readable.capitalize()} escalated from "
                f"{ch['old_priority']} to {ch['new_priority']} "
                f"due to increased pressure."
            )
        if storage_delta > 10:
            return (
                f"Modified scenario achieves {storage_delta:.1f}% "
                f"more storage reduction."
            )
        return "Recommendations are stable across this parameter change."
