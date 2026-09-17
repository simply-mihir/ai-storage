"""Technique domain model — structured metadata for storage optimization techniques."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class TechniqueCategory(StrEnum):
    STORAGE = "STORAGE"
    DATABASE = "DATABASE"
    PERFORMANCE = "PERFORMANCE"
    ANALYTICS = "ANALYTICS"


class ComplexityLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ImpactLevel(StrEnum):
    HIGH_IMPROVEMENT = "HIGH_IMPROVEMENT"
    MODERATE_IMPROVEMENT = "MODERATE_IMPROVEMENT"
    SLIGHT_IMPROVEMENT = "SLIGHT_IMPROVEMENT"
    NEUTRAL = "NEUTRAL"
    SLIGHT_INCREASE = "SLIGHT_INCREASE"
    MODERATE_INCREASE = "MODERATE_INCREASE"


class Technique(BaseModel):
    """A single storage optimization technique with its full metadata.

    Loaded from the knowledge base YAML. The rule engine uses the
    `solves`, `applicable_when`, `prerequisites`, and `conflicts_with`
    fields to decide whether and how strongly a technique applies.
    """

    id: str
    name: str
    category: TechniqueCategory
    description: str
    solves: list[str]
    applicable_when: dict[str, list[str]]
    benefits: list[str]
    disadvantages: list[str]
    implementation_complexity: ComplexityLevel
    storage_impact: ImpactLevel
    performance_impact: ImpactLevel
    cost_impact: ImpactLevel
    scalability_impact: ImpactLevel
    prerequisites: list[str]
    conflicts_with: list[str]
    not_recommended_when: list[str]
