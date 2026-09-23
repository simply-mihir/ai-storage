"""Report payload builder — assembles a structured consultant report from pipeline outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from storage_advisor.analytics.trajectory import GrowthTrajectorySimulator
from storage_advisor.architecture.builder import ArchitectureBuilder, ArchitectureOutput
from storage_advisor.detection.problem_detector import detect_problems
from storage_advisor.domain.problems import DetectedProblem, ProblemSeverity
from storage_advisor.domain.recommendations import Recommendation
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import ImpactReport, estimate_impact
from storage_advisor.kb.loader import project_graph
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.profiling.workload_profiler import (
    WorkloadProfile,
    profile_workload,
)
from storage_advisor.recommendation.recommendation_engine import (
    run_recommendation_engine,
)

_SEVERITY_ORDER = {
    ProblemSeverity.CRITICAL: 0,
    ProblemSeverity.HIGH: 1,
    ProblemSeverity.MEDIUM: 2,
    ProblemSeverity.LOW: 3,
}

_COMPLEXITY_EFFORT: dict[str, str] = {
    "LOW": "1-3 days",
    "MEDIUM": "4-10 days",
    "HIGH": "11-20 days",
}

_COMPLEXITY_BAND: dict[str, str] = {
    "LOW": "low",
    "MEDIUM": "medium",
    "HIGH": "high",
}


class RoadmapStep(BaseModel):
    phase: int
    phase_label: str
    technique_id: str
    technique_name: str
    effort_band: str
    effort_estimate: str
    acceptance_criteria: str


class RiskItem(BaseModel):
    problem_id: str
    name: str
    severity: str
    addressed: bool


class TradeOff(BaseModel):
    technique_id: str
    trade_off: str


class ScalabilityPoint(BaseModel):
    month: int
    trigger: str
    description: str


class ReportPayload(BaseModel):
    executive_summary: str
    architecture_overview: str
    storage_strategy: list[dict[str, str]]
    recommended_techniques: list[dict[str, object]]
    implementation_roadmap: list[RoadmapStep]
    risk_analysis: list[RiskItem]
    trade_offs: list[TradeOff]
    scalability_analysis: str
    scalability_points: list[ScalabilityPoint]
    alternatives: list[dict[str, object]]
    impact_disclaimer: str = Field(
        default="All estimates are MODEL-BASED projections using documented "
        "assumptions. Actual results depend on workload characteristics, "
        "data distribution, access patterns, and implementation details.",
    )


def _build_executive_summary(
    problems: list[DetectedProblem],
    recommendations: list[Recommendation],
    impact: ImpactReport,
) -> str:
    top_problems = sorted(problems, key=lambda p: _SEVERITY_ORDER.get(p.severity, 3))[:3]
    top_recs = sorted(recommendations, key=lambda r: -r.alignment_score)[:3]

    problem_lines = ", ".join(f"{p.name} ({p.severity})" for p in top_problems)
    rec_lines = ", ".join(
        f"{r.technique_name} (alignment {r.alignment_score:.2f})" for r in top_recs
    )

    storage_pct = impact.storage.estimated_reduction_pct
    cost_pct = impact.cost.estimated_savings_pct
    latency_pct = impact.latency.estimated_improvement_pct

    return (
        f"Analysis identified {len(problems)} architectural pressures, "
        f"led by {problem_lines}. "
        f"The top recommendations are {rec_lines}. "
        f"Projected impact: {storage_pct:.0f}% storage reduction, "
        f"{cost_pct:.0f}% cost savings, {latency_pct:.0f}% latency improvement. "
        f"All estimates are MODEL-BASED projections using documented assumptions."
    )


def _build_architecture_overview(
    architecture: ArchitectureOutput,
    scenario: Scenario,
) -> str:
    parts: list[str] = []
    domain_map: dict[str, list[str]] = {}
    for comp in architecture.components:
        domain_map.setdefault(comp.workload_domain, []).append(comp.service)

    for domain, services in domain_map.items():
        svc_list = ", ".join(services)
        parts.append(f"{domain.title()} workload: {svc_list}.")

    if not parts:
        return "No concrete architecture components recommended."

    return " ".join(parts) + f" Domain: {scenario.business_domain}."


def _build_storage_strategy(
    architecture: ArchitectureOutput,
) -> list[dict[str, str]]:
    return [
        {
            "data_class": comp.workload_domain,
            "placement": comp.service,
            "priority": comp.priority,
        }
        for comp in architecture.components
    ]


def _build_recommended_techniques(
    recommendations: list[Recommendation],
) -> list[dict[str, object]]:
    sorted_recs = sorted(
        recommendations,
        key=lambda r: (
            0 if r.priority == "REQUIRED" else (1 if r.priority == "RECOMMENDED" else 2),
            -r.alignment_score,
        ),
    )
    return [
        {
            "technique_id": r.technique_id,
            "technique_name": r.technique_name,
            "priority": r.priority,
            "alignment_score": r.alignment_score,
            "problems_solved": r.problems_solved,
            "complexity": r.implementation_complexity,
        }
        for r in sorted_recs
    ]


def _build_roadmap(
    recommendations: list[Recommendation],
) -> list[RoadmapStep]:
    graph = project_graph()
    rec_ids = {r.technique_id for r in recommendations}
    rec_map = {r.technique_id: r for r in recommendations}

    requires_dag: dict[str, set[str]] = {}
    for r in recommendations:
        reqs_in_scope = set()
        for prereq in r.prerequisites:
            if prereq in rec_ids:
                reqs_in_scope.add(prereq)
            else:
                for node in graph.nodes:
                    if node.startswith(prereq + ".") and node in rec_ids:
                        reqs_in_scope.add(node)
        requires_dag[r.technique_id] = reqs_in_scope

    phase_0: list[str] = []
    phase_1: list[str] = []
    phase_2: list[str] = []

    for tid, r in rec_map.items():
        unmet = requires_dag.get(tid, set())
        complexity = r.implementation_complexity.upper()
        if complexity == "LOW" and not unmet:
            phase_0.append(tid)
        elif not unmet or all(dep in phase_0 for dep in unmet):
            phase_1.append(tid)
        else:
            phase_2.append(tid)

    phase_1 = [t for t in phase_1 if t not in phase_0]
    phase_2 = [t for t in phase_2 if t not in phase_0 and t not in phase_1]

    for tid in rec_ids:
        if tid not in phase_0 and tid not in phase_1 and tid not in phase_2:
            phase_2.append(tid)

    steps: list[RoadmapStep] = []
    phase_map = [
        (0, "Quick Wins", phase_0),
        (1, "Foundations", phase_1),
        (2, "Scale", phase_2),
    ]

    for phase_num, phase_label, tids in phase_map:
        for tid in tids:
            r = rec_map[tid]
            complexity = r.implementation_complexity.upper()
            steps.append(RoadmapStep(
                phase=phase_num,
                phase_label=phase_label,
                technique_id=tid,
                technique_name=r.technique_name,
                effort_band=_COMPLEXITY_BAND.get(complexity, "medium"),
                effort_estimate=_COMPLEXITY_EFFORT.get(complexity, "4-10 days"),
                acceptance_criteria=(
                    f"{r.technique_name} deployed and verified against "
                    f"{', '.join(r.problems_solved[:2]) or 'baseline'}"
                ),
            ))

    return steps


def _build_risk_analysis(
    problems: list[DetectedProblem],
    recommendations: list[Recommendation],
) -> list[RiskItem]:
    solved_problems: set[str] = set()
    for r in recommendations:
        solved_problems.update(r.problems_solved)

    return [
        RiskItem(
            problem_id=p.problem_id,
            name=p.name,
            severity=p.severity,
            addressed=p.problem_id in solved_problems,
        )
        for p in sorted(problems, key=lambda p: _SEVERITY_ORDER.get(p.severity, 3))
    ]


def _build_trade_offs(
    recommendations: list[Recommendation],
) -> list[TradeOff]:
    trade_offs: list[TradeOff] = []
    for r in sorted(recommendations, key=lambda r: -r.alignment_score)[:3]:
        if r.disadvantages:
            trade_offs.append(TradeOff(
                technique_id=r.technique_id,
                trade_off=r.disadvantages[0],
            ))
    return trade_offs


def _build_scalability_analysis(
    scenario: Scenario,
    profile: WorkloadProfile,
) -> tuple[str, list[ScalabilityPoint]]:
    try:
        simulator = GrowthTrajectorySimulator()
        result = simulator.simulate(scenario, months=24)
        points = [
            ScalabilityPoint(
                month=tp.month,
                trigger=tp.trigger,
                description=tp.description,
            )
            for tp in result.tipping_points[:5]
        ]
        concurrency = (
            f"At {scenario.concurrent_users:,} concurrent users, "
            f"the workload operates at "
            f"{'extreme' if scenario.concurrent_users >= 250_000 else 'high' if scenario.concurrent_users >= 25_000 else 'moderate' if scenario.concurrent_users >= 1_000 else 'low'} "
            f"concurrency."
        )
        return (
            f"{result.summary} {concurrency}",
            points,
        )
    except (ValueError, KeyError, TypeError):
        return (
            f"Scalability analysis unavailable. Concurrent users: {scenario.concurrent_users:,}.",
            [],
        )


def build_report(scenario: Scenario) -> ReportPayload:
    """Build a complete report payload from a scenario."""
    techniques = load_techniques()
    profile = profile_workload(scenario)
    problems = detect_problems(scenario, profile)
    result = run_recommendation_engine(scenario, techniques)
    impact = estimate_impact(scenario, result.recommendations)
    builder = ArchitectureBuilder()
    architecture = builder.build(scenario, result)

    scalability_text, scalability_points = _build_scalability_analysis(
        scenario, profile,
    )

    return ReportPayload(
        executive_summary=_build_executive_summary(problems, result.recommendations, impact),
        architecture_overview=_build_architecture_overview(architecture, scenario),
        storage_strategy=_build_storage_strategy(architecture),
        recommended_techniques=_build_recommended_techniques(result.recommendations),
        implementation_roadmap=_build_roadmap(result.recommendations),
        risk_analysis=_build_risk_analysis(problems, result.recommendations),
        trade_offs=_build_trade_offs(result.recommendations),
        scalability_analysis=scalability_text,
        scalability_points=scalability_points,
        alternatives=[
            {
                "label": a.label,
                "focus": a.focus,
                "trade_off": a.trade_off,
                "technique_count": len(a.techniques),
            }
            for a in result.alternatives
        ],
    )
