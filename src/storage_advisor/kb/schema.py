"""Knowledge Base v2 Pydantic models.

Defines the family/variant schema with signed impact scores,
avoid_when conditions, company references, and relationship edges.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FamilyCategory(StrEnum):
    """Categories for technique families in KB v2."""

    STORAGE = "storage"
    DATABASE = "database"
    PERFORMANCE = "performance"
    ANALYTICS = "analytics"
    RELIABILITY = "reliability"
    ARCHITECTURE = "architecture"
    SECURITY = "security"


class Complexity(StrEnum):
    """Implementation complexity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Impacts(BaseModel):
    """Signed impact scores from -5 (severe overhead) to +5 (major improvement).

    Negative values indicate the technique introduces overhead in that
    dimension; positive values indicate improvement.
    """

    storage: int = Field(0, ge=-5, le=5)
    performance: int = Field(0, ge=-5, le=5)
    cost: int = Field(0, ge=-5, le=5)
    scalability: int = Field(0, ge=-5, le=5)
    security: int = Field(0, ge=-5, le=5)


class AvoidWhen(BaseModel):
    """A condition under which a technique should NOT be used, with a reason."""

    condition: str
    reason: str


class Company(BaseModel):
    """A real-world company example using this technique."""

    name: str
    context: str


class Variant(BaseModel):
    """A specific sub-technique that inherits from and optionally overrides its family.

    All fields except id and name are optional — unset fields inherit
    from the parent family during flattening.
    """

    id: str
    name: str
    summary: str | None = None
    mechanism: str | None = None
    solves: list[str] | None = None
    synergies_with: list[str] | None = None
    conflicts_with: list[str] | None = None
    requires: list[str] | None = None
    avoid_when: list[AvoidWhen] | None = None
    applicable_when: dict[str, list[str]] | None = None
    implementation_complexity: Complexity | None = None
    impacts: Impacts | None = None
    benefits: list[str] | None = None
    disadvantages: list[str] | None = None
    companies: list[Company] | None = None


class Family(BaseModel):
    """A technique family — the base record from which variants inherit.

    A family with no variants produces one EffectiveTechnique with id
    equal to the family id. A family with variants produces one
    EffectiveTechnique per variant, each with id ``<family_id>.<variant_id>``.
    """

    schema_version: int = Field(..., alias="schema_version")
    id: str
    name: str
    category: FamilyCategory
    summary: str
    mechanism: str | None = None
    solves: list[str] = Field(default_factory=list)
    synergies_with: list[str] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    avoid_when: list[AvoidWhen] = Field(default_factory=list)
    applicable_when: dict[str, list[str]] = Field(default_factory=dict)
    implementation_complexity: Complexity = Complexity.MEDIUM
    impacts: Impacts = Field(default_factory=Impacts)
    benefits: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)
    companies: list[Company] = Field(default_factory=list)
    variants: list[Variant] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, v: int) -> int:
        if v != 2:
            msg = f"Expected schema_version 2, got {v}"
            raise ValueError(msg)
        return v


class EffectiveTechnique(BaseModel):
    """A fully-resolved technique record after family/variant merging.

    All fields are concrete — no optionals except empty lists.
    Produced by the loader's ``flatten()`` function.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    category: FamilyCategory
    summary: str
    mechanism: str
    solves: list[str]
    synergies_with: list[str]
    conflicts_with: list[str]
    requires: list[str]
    avoid_when: list[AvoidWhen]
    applicable_when: dict[str, list[str]]
    implementation_complexity: Complexity
    impacts: Impacts
    benefits: list[str]
    disadvantages: list[str]
    companies: list[Company]
