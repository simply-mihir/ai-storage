"""EDA module forwarding."""
from __future__ import annotations

from storage_advisor.analytics.eda import (
    correlation_matrix,
    industry_category_heatdata,
    savings_distributions,
    technique_cooccurrence,
    technique_frequency,
)

__all__ = [
    "correlation_matrix",
    "industry_category_heatdata",
    "savings_distributions",
    "technique_cooccurrence",
    "technique_frequency",
]
