"""Growth Trajectory Simulator — projects architecture evolution over time."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from storage_advisor.architecture.builder import ArchitectureBuilder
from storage_advisor.detection.problem_detector import detect_problems
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.integrations.pricing import AWSPricingClient
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.profiling.workload_profiler import profile_workload
from storage_advisor.recommendation.recommendation_engine import (
    run_recommendation_engine,
)

logger = logging.getLogger(__name__)


@dataclass
class MonthSnapshot:
    month: int
    users: int
    storage_gb: float
    daily_growth_gb: float
    problems: list[str]
    problem_severities: dict[str, str]
    top_techniques: list[str]
    required_techniques: list[str]
    architecture_services: list[str]
    estimated_storage_gb: float
    estimated_cost_usd: float
    real_cost_usd: float
    latency_ms: float


@dataclass
class TippingPoint:
    month: int
    trigger: str
    old_state: str
    new_state: str
    technique_id: str
    severity: str
    description: str


@dataclass
class TrajectoryResult:
    snapshots: list[MonthSnapshot]
    tipping_points: list[TippingPoint]
    months_simulated: int
    starting_storage_gb: float
    ending_storage_gb: float
    starting_cost_usd: float
    ending_cost_usd: float
    architecture_stable_until: int
    summary: str


class GrowthTrajectorySimulator:

    def __init__(self) -> None:
        self._techniques = load_techniques()
        self._builder = ArchitectureBuilder()
        self._pricing = AWSPricingClient()

    def simulate(
        self,
        scenario: Scenario,
        months: int = 24,
        user_growth_rate: float = 0.05,
    ) -> TrajectoryResult:
        snapshots: list[MonthSnapshot] = []
        tipping_points: list[TippingPoint] = []
        seen_tp_pairs: set[tuple[str, str]] = set()

        for month in range(1, months + 1):
            try:
                snapshot = self._simulate_month(
                    scenario, month, user_growth_rate,
                )
                snapshots.append(snapshot)

                if len(snapshots) >= 2:
                    prev = snapshots[-2]
                    self._detect_tipping_points(
                        prev, snapshot, month, tipping_points, seen_tp_pairs,
                    )

                if month % 6 == 0:
                    logger.info(
                        "Month %d: %,d users, %.0f GB, $%.0f/mo",
                        month, snapshot.users, snapshot.storage_gb,
                        snapshot.real_cost_usd,
                    )
            except Exception:
                logger.warning("Month %d simulation failed, skipping", month, exc_info=True)
                if snapshots:
                    filler = MonthSnapshot(
                        month=month,
                        users=snapshots[-1].users,
                        storage_gb=snapshots[-1].storage_gb,
                        daily_growth_gb=snapshots[-1].daily_growth_gb,
                        problems=snapshots[-1].problems,
                        problem_severities=snapshots[-1].problem_severities,
                        top_techniques=snapshots[-1].top_techniques,
                        required_techniques=snapshots[-1].required_techniques,
                        architecture_services=snapshots[-1].architecture_services,
                        estimated_storage_gb=snapshots[-1].estimated_storage_gb,
                        estimated_cost_usd=snapshots[-1].estimated_cost_usd,
                        real_cost_usd=snapshots[-1].real_cost_usd,
                        latency_ms=snapshots[-1].latency_ms,
                    )
                    snapshots.append(filler)

        stable_until = (
            tipping_points[0].month if tipping_points else months
        )

        ending_storage = snapshots[-1].storage_gb if snapshots else scenario.current_storage_gb
        ending_cost = snapshots[-1].real_cost_usd if snapshots else 0.0
        starting_cost = snapshots[0].real_cost_usd if snapshots else 0.0

        final_users = int(
            scenario.expected_users * (1 + user_growth_rate) ** months
        )
        summary = self._build_summary(
            scenario, months, final_users, ending_storage,
            ending_cost, tipping_points, snapshots,
        )

        return TrajectoryResult(
            snapshots=snapshots,
            tipping_points=tipping_points,
            months_simulated=months,
            starting_storage_gb=scenario.current_storage_gb,
            ending_storage_gb=ending_storage,
            starting_cost_usd=starting_cost,
            ending_cost_usd=ending_cost,
            architecture_stable_until=stable_until,
            summary=summary,
        )

    def _simulate_month(
        self,
        scenario: Scenario,
        month: int,
        user_growth_rate: float,
    ) -> MonthSnapshot:
        current_users = int(
            scenario.expected_users * (1 + user_growth_rate) ** month
        )
        user_growth_multiplier = current_users / scenario.expected_users
        current_daily_growth = scenario.daily_growth_gb * user_growth_multiplier
        current_storage = (
            scenario.current_storage_gb + scenario.daily_growth_gb * 30 * month
        )
        concurrent = min(
            int(scenario.concurrent_users * (1 + user_growth_rate) ** month),
            current_users,
        )

        projected = scenario.model_copy(update={
            "expected_users": current_users,
            "concurrent_users": concurrent,
            "current_storage_gb": current_storage,
            "daily_growth_gb": current_daily_growth,
        })

        profile = profile_workload(projected)
        problems = detect_problems(projected, profile)
        result = run_recommendation_engine(projected, self._techniques)
        impact = estimate_impact(projected, result.recommendations)
        arch = self._builder.build(projected, result)
        real_cost = self._pricing.calculate_monthly_architecture_cost(
            arch, projected,
        )

        top_techniques = [
            r.technique_id
            for r in sorted(
                result.recommendations,
                key=lambda r: (-1 if r.priority == "REQUIRED" else 0, -r.alignment_score),
            )[:5]
        ]
        required_techniques = [
            r.technique_id
            for r in result.recommendations
            if r.priority == "REQUIRED"
        ]

        return MonthSnapshot(
            month=month,
            users=current_users,
            storage_gb=current_storage,
            daily_growth_gb=current_daily_growth,
            problems=[p.problem_id for p in problems],
            problem_severities={p.problem_id: p.severity for p in problems},
            top_techniques=top_techniques,
            required_techniques=required_techniques,
            architecture_services=[c.service for c in arch.components],
            estimated_storage_gb=impact.storage.projected_storage_gb
            - impact.storage.estimated_reduction_gb,
            estimated_cost_usd=impact.cost.estimated_monthly_optimized_usd,
            real_cost_usd=real_cost.total_monthly_usd,
            latency_ms=impact.latency.estimated_optimized_latency_ms,
        )

    def _detect_tipping_points(
        self,
        prev: MonthSnapshot,
        curr: MonthSnapshot,
        month: int,
        tipping_points: list[TippingPoint],
        seen: set[tuple[str, str]],
    ) -> None:
        prev_required = set(prev.required_techniques)
        prev_top = set(prev.top_techniques)
        curr_required = set(curr.required_techniques)
        curr_top = set(curr.top_techniques)

        for tid in curr_required - prev_required:
            if tid in prev_top and (tid, "ESCALATION") not in seen:
                seen.add((tid, "ESCALATION"))
                tipping_points.append(TippingPoint(
                    month=month,
                    trigger=f"{tid} escalated to REQUIRED",
                    old_state=f"{tid}: RECOMMENDED",
                    new_state=f"{tid}: REQUIRED",
                    technique_id=tid,
                    severity="ESCALATION",
                    description=(
                        f"Month {month}: {tid} escalates from RECOMMENDED to "
                        f"REQUIRED as storage reaches {curr.storage_gb:,.0f} GB "
                        f"and users reach {curr.users:,}."
                    ),
                ))

        for tid in curr_top - prev_top:
            if (tid, "NEW_TECHNIQUE") not in seen:
                seen.add((tid, "NEW_TECHNIQUE"))
                tipping_points.append(TippingPoint(
                    month=month,
                    trigger=f"{tid} becomes necessary",
                    old_state="not present",
                    new_state=f"{tid}: {'REQUIRED' if tid in curr_required else 'RECOMMENDED'}",
                    technique_id=tid,
                    severity="NEW_TECHNIQUE",
                    description=(
                        f"Month {month}: {tid} enters the architecture as "
                        f"workload crosses a new threshold."
                    ),
                ))

        prev_services = set(prev.architecture_services)
        for svc in curr.architecture_services:
            if svc not in prev_services and (svc, "ARCHITECTURE_CHANGE") not in seen:
                seen.add((svc, "ARCHITECTURE_CHANGE"))
                tipping_points.append(TippingPoint(
                    month=month,
                    trigger=f"{svc} added to architecture",
                    old_state="not present",
                    new_state=f"{svc}: active",
                    technique_id=svc,
                    severity="ARCHITECTURE_CHANGE",
                    description=(
                        f"Month {month}: {svc} joins the architecture as the "
                        f"previous tier can no longer handle the load alone."
                    ),
                ))

    def _build_summary(
        self,
        scenario: Scenario,
        months: int,
        final_users: int,
        ending_storage: float,
        ending_cost: float,
        tipping_points: list[TippingPoint],
        snapshots: list[MonthSnapshot],
    ) -> str:
        tp_count = len(tipping_points)
        first_tp = tipping_points[0].month if tipping_points else months
        starting_cost = snapshots[0].real_cost_usd if snapshots else 0.0

        parts = [
            (
                f"Over {months} months, the workload grows from "
                f"{scenario.expected_users:,} to {final_users:,} users and "
                f"{scenario.current_storage_gb:,} to {ending_storage:,.0f} GB of storage. "
            )
        ]

        if tipping_points:
            parts.append(
                f"The architecture remains stable until month {first_tp}, when "
                f"{tipping_points[0].technique_id} requires escalation. "
                f"A total of {tp_count} architectural changes are required "
                f"over the period. "
            )
        else:
            parts.append(
                "The initial architecture handles the full growth period. "
            )

        parts.append(
            f"Monthly AWS costs grow from ${starting_cost:,.0f} to "
            f"${ending_cost:,.0f}."
        )

        return "".join(parts)
