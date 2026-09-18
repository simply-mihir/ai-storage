"""Rule Engine — scores each candidate technique's alignment with the scenario.

The engine evaluates two dimensions:
1. Problem coverage — how many detected problems does this technique solve?
2. Profile alignment — do the scenario's profile values match the technique's
   `applicable_when` conditions?

The output is an alignment_score (0.0-1.0), a priority, and evidence.
This is NOT a probability — it's a deterministic alignment measure.
"""

from __future__ import annotations

from storage_advisor.domain.problems import DetectedProblem, ProblemSeverity
from storage_advisor.domain.recommendations import Priority, Recommendation
from storage_advisor.domain.scenario import Scenario
from storage_advisor.domain.techniques import Technique
from storage_advisor.profiling.workload_profiler import WorkloadProfile


def _compute_problem_coverage_score(
    matched_problems: list[str],
    all_problems: list[DetectedProblem],
) -> float:
    """Score based on how many problems this technique solves, weighted by severity."""
    if not all_problems:
        return 0.0

    severity_weights = {
        ProblemSeverity.CRITICAL: 1.0,
        ProblemSeverity.HIGH: 0.8,
        ProblemSeverity.MEDIUM: 0.5,
        ProblemSeverity.LOW: 0.2,
    }

    problem_map = {p.problem_id: p for p in all_problems}
    total_weight = sum(severity_weights[p.severity] for p in all_problems)

    matched_weight = sum(
        severity_weights[problem_map[pid].severity]
        for pid in matched_problems
        if pid in problem_map
    )

    return matched_weight / total_weight if total_weight > 0 else 0.0


def _compute_profile_alignment_score(
    technique: Technique,
    profile: WorkloadProfile,
) -> float:
    """Score based on how well the profile matches the technique's applicable_when."""
    if not technique.applicable_when:
        return 0.5

    profile_dict = profile.model_dump()
    matched_conditions = 0
    total_conditions = len(technique.applicable_when)

    for field, acceptable_values in technique.applicable_when.items():
        profile_value = profile_dict.get(field)
        if profile_value is not None and profile_value in acceptable_values:
            matched_conditions += 1

    return matched_conditions / total_conditions if total_conditions > 0 else 0.5


def _determine_priority(
    alignment_score: float,
    matched_problems: list[str],
    all_problems: list[DetectedProblem],
) -> Priority:
    """Assign priority based on alignment score and problem severity."""
    problem_map = {p.problem_id: p for p in all_problems}
    high_count = 0
    has_critical = False
    for pid in matched_problems:
        p = problem_map.get(pid)
        if p is None:
            continue
        if p.severity == ProblemSeverity.CRITICAL:
            has_critical = True
        elif p.severity == ProblemSeverity.HIGH:
            high_count += 1

    if has_critical:
        return Priority.REQUIRED
    if high_count >= 2 and alignment_score >= 0.6:
        return Priority.REQUIRED
    if high_count >= 1 and alignment_score >= 0.7:
        return Priority.REQUIRED
    if alignment_score >= 0.4:
        return Priority.RECOMMENDED
    return Priority.OPTIONAL


def _build_evidence(
    technique: Technique,
    matched_problems: list[str],
    profile: WorkloadProfile,
) -> list[str]:
    """Build human-readable evidence strings."""
    evidence: list[str] = []
    profile_dict = profile.model_dump()

    for field, acceptable in technique.applicable_when.items():
        actual = profile_dict.get(field)
        if actual is not None and actual in acceptable:
            evidence.append(f"{field}={actual}")

    for pid in matched_problems:
        evidence.append(f"solves {pid}")

    return evidence


def _build_rationale(
    technique: Technique,
    matched_problems: list[str],
    priority: Priority,
) -> str:
    """Generate a concise rationale string."""
    problem_names = ", ".join(
        pid.replace("_", " ").lower() for pid in matched_problems
    )
    if priority == Priority.REQUIRED:
        return (
            f"{technique.name} is required to address: {problem_names}. "
            f"{technique.benefits[0] if technique.benefits else ''}"
        )
    if priority == Priority.RECOMMENDED:
        return (
            f"{technique.name} is recommended for: {problem_names}. "
            f"{technique.benefits[0] if technique.benefits else ''}"
        )
    return (
        f"{technique.name} may help with: {problem_names}. "
        f"{technique.benefits[0] if technique.benefits else ''}"
    )


def evaluate_candidate(
    technique: Technique,
    matched_problems: list[str],
    all_problems: list[DetectedProblem],
    profile: WorkloadProfile,
    scenario: Scenario,
) -> Recommendation:
    """Score a single candidate technique and produce a Recommendation."""
    problem_score = _compute_problem_coverage_score(matched_problems, all_problems)
    profile_score = _compute_profile_alignment_score(technique, profile)

    alignment_score = round(0.6 * problem_score + 0.4 * profile_score, 3)

    priority = _determine_priority(alignment_score, matched_problems, all_problems)
    evidence = _build_evidence(technique, matched_problems, profile)
    rationale = _build_rationale(technique, matched_problems, priority)

    return Recommendation(
        technique_id=technique.id,
        technique_name=technique.name,
        category=technique.category,
        priority=priority,
        alignment_score=alignment_score,
        problems_solved=matched_problems,
        rationale=rationale,
        evidence=evidence,
        benefits=technique.benefits,
        disadvantages=technique.disadvantages,
        implementation_complexity=technique.implementation_complexity,
        prerequisites=technique.prerequisites,
        conflicts_with=technique.conflicts_with,
        conditions=technique.not_recommended_when,
    )


def evaluate_all_candidates(
    candidates: list[tuple[Technique, list[str]]],
    all_problems: list[DetectedProblem],
    profile: WorkloadProfile,
    scenario: Scenario,
) -> list[Recommendation]:
    """Score all candidates and return recommendations sorted by alignment score."""
    recommendations = [
        evaluate_candidate(tech, matched, all_problems, profile, scenario)
        for tech, matched in candidates
    ]
    recommendations.sort(key=lambda r: r.alignment_score, reverse=True)
    return recommendations
