"""Prometheus metrics collector and text-format exporter.

Implements requests_total counter, stage_duration_seconds summary,
and ai_fallback_tier counter without external dependencies.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Thread-safe in-memory Prometheus metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # requests_total{(endpoint, method, status)} -> count
        self._requests: dict[tuple[str, str, str], int] = defaultdict(int)
        # stage_duration_seconds{stage} -> list of durations in seconds
        self._stage_durations: dict[str, list[float]] = defaultdict(list)
        # ai_fallback_tier{tier} -> count
        self._ai_fallback: dict[str, int] = defaultdict(int)
        # Initialize default tiers to 0
        for tier in ("bedrock", "groq", "structured_fallback"):
            self._ai_fallback[tier] = 0

    def record_request(self, endpoint: str, method: str, status: int | str) -> None:
        """Increment the requests_total counter."""
        with self._lock:
            key = (str(endpoint), str(method).upper(), str(status))
            self._requests[key] += 1

    def record_stage_duration(self, stage: str, duration_seconds: float) -> None:
        """Record a pipeline stage duration in seconds."""
        with self._lock:
            self._stage_durations[str(stage)].append(float(duration_seconds))

    def record_ai_fallback_tier(self, tier: str) -> None:
        """Increment the ai_fallback_tier counter."""
        with self._lock:
            self._ai_fallback[str(tier)] += 1

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._requests.clear()
            self._stage_durations.clear()
            self._ai_fallback.clear()
            for tier in ("bedrock", "groq", "structured_fallback"):
                self._ai_fallback[tier] = 0

    def export_prometheus_text(self) -> str:
        """Format metrics in the standard Prometheus exposition format."""
        with self._lock:
            lines: list[str] = []

            # 1. requests_total
            lines.append("# HELP requests_total Total count of HTTP requests processed.")
            lines.append("# TYPE requests_total counter")
            if not self._requests:
                # Emit placeholder comment or zero count
                lines.append('requests_total{endpoint="/health",method="GET",status="200"} 0')
            else:
                for (endpoint, method, status), count in sorted(self._requests.items()):
                    lines.append(f'requests_total{{endpoint="{endpoint}",method="{method}",status="{status}"}} {count}')

            lines.append("")

            # 2. stage_duration_seconds summary
            lines.append("# HELP stage_duration_seconds Summary of pipeline stage durations in seconds.")
            lines.append("# TYPE stage_duration_seconds summary")
            if not self._stage_durations:
                for default_stage in ("profiling", "problem_detection", "recommendation_engine", "impact_estimation", "architecture_build"):
                    lines.append(f'stage_duration_seconds_sum{{stage="{default_stage}"}} 0.0')
                    lines.append(f'stage_duration_seconds_count{{stage="{default_stage}"}} 0')
            else:
                for stage, samples in sorted(self._stage_durations.items()):
                    count = len(samples)
                    total_sum = sum(samples)
                    sorted_samples = sorted(samples)

                    def quantile(q: float) -> float:
                        if not sorted_samples:
                            return 0.0
                        idx = int(q * (len(sorted_samples) - 1))
                        return sorted_samples[idx]

                    p50 = quantile(0.50)
                    p90 = quantile(0.90)
                    p99 = quantile(0.99)

                    lines.append(f'stage_duration_seconds{{stage="{stage}",quantile="0.5"}} {p50:.6f}')
                    lines.append(f'stage_duration_seconds{{stage="{stage}",quantile="0.9"}} {p90:.6f}')
                    lines.append(f'stage_duration_seconds{{stage="{stage}",quantile="0.99"}} {p99:.6f}')
                    lines.append(f'stage_duration_seconds_sum{{stage="{stage}"}} {total_sum:.6f}')
                    lines.append(f'stage_duration_seconds_count{{stage="{stage}"}} {count}')

            lines.append("")

            # 3. ai_fallback_tier counter
            lines.append("# HELP ai_fallback_tier Total count of AI explanation tier invocations.")
            lines.append("# TYPE ai_fallback_tier counter")
            for tier, count in sorted(self._ai_fallback.items()):
                lines.append(f'ai_fallback_tier{{tier="{tier}"}} {count}')

            lines.append("")
            return "\n".join(lines)


# Global singleton collector
metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Return the global metrics collector singleton."""
    return metrics_collector
