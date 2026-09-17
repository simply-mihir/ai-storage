"""Scenario domain model — the complete validated description of a user's data-storage workload.

A Scenario is the input to the entire recommendation pipeline. Every field
exists because it meaningfully influences at least one architectural decision.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, model_validator


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

_DOMAIN_ALIASES: dict[str, str] = {
    "E_COMMERCE": "ECOMMERCE",
    "E_COMM": "ECOMMERCE",
    "FIN_TECH": "FINTECH",
    "HEALTH_CARE": "HEALTHCARE",
    "TELE_COMMUNICATION": "TELECOMMUNICATION",
    "TELECOM": "TELECOMMUNICATION",
    "PCI": "PCI_DSS",
}


def _normalize_enum_value(v: object) -> object:
    """Uppercase and strip string inputs so enum matching is case-insensitive."""
    if isinstance(v, str):
        normalized = v.strip().upper().replace("-", "_").replace(" ", "_")
        return _DOMAIN_ALIASES.get(normalized, normalized)
    return v


def _normalize_enum_list(v: object) -> object:
    """Apply case normalization to each element in a list."""
    if isinstance(v, list):
        return [_normalize_enum_value(item) for item in v]
    return v


NormalizedStr = Annotated[str, BeforeValidator(_normalize_enum_value)]

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BusinessDomain(StrEnum):
    ECOMMERCE = "ECOMMERCE"
    FINTECH = "FINTECH"
    HEALTHCARE = "HEALTHCARE"
    MEDIA = "MEDIA"
    SAAS = "SAAS"
    IOT = "IOT"
    GAMING = "GAMING"
    EDUCATION = "EDUCATION"
    GOVERNMENT = "GOVERNMENT"
    MANUFACTURING = "MANUFACTURING"
    LOGISTICS = "LOGISTICS"
    RETAIL = "RETAIL"
    TELECOMMUNICATION = "TELECOMMUNICATION"
    AGRICULTURE = "AGRICULTURE"
    ENERGY = "ENERGY"
    RESEARCH = "RESEARCH"
    AI = "AI"
    OTHER = "OTHER"


class CompanySize(StrEnum):
    STARTUP = "STARTUP"
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    ENTERPRISE = "ENTERPRISE"


class Intensity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AccessPattern(StrEnum):
    RANDOM = "RANDOM"
    SEQUENTIAL = "SEQUENTIAL"
    MIXED = "MIXED"


class BudgetLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DataType(StrEnum):
    TEXT = "TEXT"
    IMAGES = "IMAGES"
    VIDEOS = "VIDEOS"
    AUDIO = "AUDIO"
    DOCUMENTS = "DOCUMENTS"
    TRANSACTIONS = "TRANSACTIONS"
    LOGS = "LOGS"
    SENSOR_DATA = "SENSOR_DATA"
    TIME_SERIES = "TIME_SERIES"
    GPS_DATA = "GPS_DATA"
    CLICKSTREAM = "CLICKSTREAM"
    EMBEDDINGS = "EMBEDDINGS"
    ML_FEATURES = "ML_FEATURES"


class ComplianceType(StrEnum):
    NONE = "NONE"
    HIPAA = "HIPAA"
    GDPR = "GDPR"
    SOC2 = "SOC2"
    PCI_DSS = "PCI_DSS"


# ---------------------------------------------------------------------------
# Scenario Model
# ---------------------------------------------------------------------------

class Scenario(BaseModel):
    """Complete workload scenario for architectural analysis.

    Every field is validated on construction. Enum fields accept
    case-insensitive strings (e.g. "high", "High", "HIGH" all become HIGH).
    """

    model_config = {"str_strip_whitespace": True, "use_enum_values": True}

    # -- Business ----------------------------------------------------------
    business_domain: Annotated[BusinessDomain, BeforeValidator(_normalize_enum_value)]
    company_size: Annotated[CompanySize, BeforeValidator(_normalize_enum_value)]

    # -- Scale -------------------------------------------------------------
    expected_users: Annotated[int, Field(ge=1, description="Total expected user population")]
    concurrent_users: Annotated[int, Field(ge=1, description="Simultaneous active users")]
    current_storage_gb: Annotated[float, Field(gt=0, description="Current stored data in GB")]
    daily_growth_gb: Annotated[float, Field(ge=0, description="New data per day in GB")]

    # -- Data profile ------------------------------------------------------
    data_types: Annotated[list[Annotated[DataType, BeforeValidator(_normalize_enum_value)]], BeforeValidator(_normalize_enum_list), Field(min_length=1, description="At least one data type")]
    structured_data_pct: Annotated[float, Field(ge=0, le=100)]
    semi_structured_data_pct: Annotated[float, Field(ge=0, le=100)]
    unstructured_data_pct: Annotated[float, Field(ge=0, le=100)]

    # -- Workload ----------------------------------------------------------
    read_intensity: Annotated[Intensity, BeforeValidator(_normalize_enum_value)]
    write_intensity: Annotated[Intensity, BeforeValidator(_normalize_enum_value)]
    access_pattern: Annotated[AccessPattern, BeforeValidator(_normalize_enum_value)]

    # -- Performance -------------------------------------------------------
    latency_requirement_ms: Annotated[float, Field(gt=0, description="Max acceptable latency in ms")]

    # -- Reliability -------------------------------------------------------
    availability_requirement: Annotated[float, Field(ge=90, le=100, description="Availability as percentage")]
    rto_minutes: Annotated[float, Field(ge=0, description="Recovery Time Objective")]
    rpo_minutes: Annotated[float, Field(ge=0, description="Recovery Point Objective")]

    # -- Retention ---------------------------------------------------------
    retention_years: Annotated[float, Field(ge=0)]

    # -- Business constraints ----------------------------------------------
    budget_level: Annotated[BudgetLevel, BeforeValidator(_normalize_enum_value)]
    analytics_required: bool
    real_time_processing_required: bool

    # -- Security ----------------------------------------------------------
    sensitive_data: bool
    encryption_required: bool
    compliance_requirements: Annotated[list[Annotated[ComplianceType, BeforeValidator(_normalize_enum_value)]], BeforeValidator(_normalize_enum_list)]

    # -- Cross-field validators --------------------------------------------

    @model_validator(mode="after")
    def validate_concurrent_users(self) -> Scenario:
        if self.concurrent_users > self.expected_users:
            raise ValueError(
                f"Concurrent users ({self.concurrent_users}) cannot exceed "
                f"expected users ({self.expected_users})"
            )
        return self

    @model_validator(mode="after")
    def validate_data_percentages_sum(self) -> Scenario:
        total = (
            self.structured_data_pct
            + self.semi_structured_data_pct
            + self.unstructured_data_pct
        )
        if abs(total - 100.0) > 0.01:
            raise ValueError(
                f"Data percentages must sum to 100 (got {total:.2f}): "
                f"structured={self.structured_data_pct}, "
                f"semi_structured={self.semi_structured_data_pct}, "
                f"unstructured={self.unstructured_data_pct}"
            )
        return self
