"""Smoke tests for chart generation — verify figures are produced without error."""

import plotly.graph_objects as go

from storage_advisor.analytics.store import AnalyticsStore
from storage_advisor.analytics.charts import all_charts


PARQUET_PATH = "data/synthetic/scenarios.parquet"
EXPECTED_KEYS = {
    "kpi_cards", "technique_frequency", "domain_comparison",
    "savings_scatter", "cooccurrence_heatmap", "cooccurrence_network",
}


class TestAllCharts:
    def test_returns_six_keys(self):
        store = AnalyticsStore(PARQUET_PATH)
        charts = all_charts(store)
        assert set(charts.keys()) == EXPECTED_KEYS

    def test_all_values_are_figures(self):
        store = AnalyticsStore(PARQUET_PATH)
        charts = all_charts(store)
        for name, fig in charts.items():
            assert isinstance(fig, go.Figure), f"{name} is not a Figure"

    def test_no_exceptions_on_full_dataset(self):
        store = AnalyticsStore(PARQUET_PATH)
        charts = all_charts(store)
        for name, fig in charts.items():
            assert fig.data is not None, f"{name} has no data"
