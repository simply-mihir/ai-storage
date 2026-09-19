"""Confidence bands for impact estimates based on synthetic dataset variance."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from storage_advisor.analytics.store import AnalyticsStore
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import ImpactReport


@dataclass
class ConfidenceBand:
    metric: str
    point_estimate: float
    low: float
    high: float
    percentile_25: float
    percentile_75: float
    sample_size: int
    confidence_note: str


@dataclass
class BandedImpactEstimate:
    storage_band: ConfidenceBand
    cost_band: ConfidenceBand
    latency_band: ConfidenceBand
    disclaimer: str


class ConfidenceEstimator:

    def __init__(
        self,
        parquet_path: str = "data/synthetic/scenarios.parquet",
        store: AnalyticsStore | None = None,
    ) -> None:
        self._store = store or AnalyticsStore(parquet_path)

    def estimate_with_bands(
        self,
        scenario: Scenario,
        point_estimates: ImpactReport,
    ) -> BandedImpactEstimate:
        df = self._find_similar(scenario)

        storage_band = self._build_band(
            "storage_reduction",
            point_estimates.storage.estimated_reduction_pct,
            df["storage_reduction_pct"].values,
        )
        cost_band = self._build_band(
            "cost_reduction",
            point_estimates.cost.estimated_savings_pct,
            df["cost_reduction_pct"].values,
        )
        latency_band = self._build_band(
            "latency_improvement",
            point_estimates.latency.estimated_improvement_pct,
            df["latency_improvement_pct"].values,
        )

        return BandedImpactEstimate(
            storage_band=storage_band,
            cost_band=cost_band,
            latency_band=latency_band,
            disclaimer=(
                "Ranges represent the 25th–75th percentile of outcomes "
                "from similar synthetic scenarios. Actual results depend on "
                "implementation quality, data access patterns, and "
                "operational configuration."
            ),
        )

    def _find_similar(self, scenario: Scenario):
        domain = scenario.business_domain.lower()
        read_int = scenario.read_intensity
        users = scenario.expected_users
        growth = scenario.daily_growth_gb

        sql_strict = f"""
            SELECT storage_reduction_pct, cost_reduction_pct,
                   latency_improvement_pct
            FROM scenarios
            WHERE domain = '{domain}'
              AND read_intensity = '{read_int}'
              AND users BETWEEN {users // 5} AND {users * 5}
              AND daily_growth_gb BETWEEN {growth / 3} AND {growth * 3}
        """
        df = self._store.query(sql_strict)
        if len(df) >= 10:
            return df

        sql_domain = f"""
            SELECT storage_reduction_pct, cost_reduction_pct,
                   latency_improvement_pct
            FROM scenarios
            WHERE domain = '{domain}'
        """
        df = self._store.query(sql_domain)
        if len(df) >= 10:
            return df

        return self._store.query(
            "SELECT storage_reduction_pct, cost_reduction_pct, "
            "latency_improvement_pct FROM scenarios"
        )

    def _build_band(
        self,
        metric: str,
        point_estimate: float,
        values: np.ndarray,
    ) -> ConfidenceBand:
        p25 = float(np.percentile(values, 25))
        p75 = float(np.percentile(values, 75))
        median = float(np.median(values))

        if median > 0:
            low = point_estimate * (p25 / median)
            high = point_estimate * (p75 / median)
        else:
            low = p25
            high = p75

        low = max(0.0, low)
        high = min(100.0, high)
        if low > high:
            low, high = high, low

        n = len(values)
        if n >= 50:
            note = f"Based on {n} similar scenarios"
        elif n >= 10:
            note = f"Based on {n} scenarios (moderate confidence)"
        else:
            note = f"Based on full dataset ({n} scenarios, low confidence)"

        return ConfidenceBand(
            metric=metric,
            point_estimate=point_estimate,
            low=round(low, 2),
            high=round(high, 2),
            percentile_25=round(p25, 2),
            percentile_75=round(p75, 2),
            sample_size=n,
            confidence_note=note,
        )
