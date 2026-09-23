"""Observability package."""

from storage_advisor.observability.metrics import (
    MetricsCollector,
    get_metrics_collector,
    metrics_collector,
)

__all__ = [
    "MetricsCollector",
    "get_metrics_collector",
    "metrics_collector",
]
