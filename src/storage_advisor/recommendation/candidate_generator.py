"""Candidate Generator — matches detected problems to applicable techniques.

A technique becomes a candidate if at least one of its `solves` entries
matches a detected problem ID. This is the first filter: it produces a
broad list that the Rule Engine then scores and the Constraint Filter prunes.
"""

from __future__ import annotations

from storage_advisor.domain.problems import DetectedProblem
from storage_advisor.domain.techniques import Technique


def generate_candidates(
    problems: list[DetectedProblem],
    techniques: list[Technique],
) -> list[tuple[Technique, list[str]]]:
    """Return techniques that solve at least one detected problem.

    Returns a list of (technique, matched_problem_ids) tuples.
    """
    problem_ids = {p.problem_id for p in problems}

    candidates: list[tuple[Technique, list[str]]] = []
    for technique in techniques:
        matched = [pid for pid in technique.solves if pid in problem_ids]
        if matched:
            candidates.append((technique, matched))

    return candidates
