"""Recommendation and Strategy domain models — the engine's output."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Priority(StrEnum):
    REQUIRED = "REQUIRED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"


class Recommendation(BaseModel):
    """A single technique recommendation with full rationale."""

    technique_id: str
    technique_name: str
    category: str
    priority: Priority
    alignment_score: float
    problems_solved: list[str]
    rationale: str
    evidence: list[str]
    benefits: list[str]
    disadvantages: list[str]
    implementation_complexity: str
    prerequisites: list[str]
    conflicts_with: list[str]
    conditions: list[str]


class Strategy(BaseModel):
    """Coherent architecture strategy — recommendations grouped by workload domain."""

    transactional: list[Recommendation] = []
    object_storage: list[Recommendation] = []
    caching: list[Recommendation] = []
    analytics: list[Recommendation] = []
    archival: list[Recommendation] = []
    security: list[Recommendation] = []
    general: list[Recommendation] = []


class AlternativeStrategy(BaseModel):
    """An alternative architecture strategy with different trade-offs."""

    label: str
    focus: str
    techniques: list[Recommendation]
    trade_off: str
    estimated_cost_delta: str


class RecommendationResult(BaseModel):
    """Complete output of the recommendation pipeline."""

    scenario_summary: dict[str, object]
    detected_problems: list[dict[str, object]]
    recommendations: list[Recommendation]
    strategy: Strategy
    alternatives: list[AlternativeStrategy] = []
    assumptions: list[str]
    engine_version: str = "1.0.0"
    knowledge_base_version: str = "1.0.0"
