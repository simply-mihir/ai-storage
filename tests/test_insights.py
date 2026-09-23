"""Tests for the Insights module — Plotly figure generation."""

import json

import pytest

from storage_advisor.analytics.generator import ScenarioGenerator
from storage_advisor.analytics.insights import (
    all_figures,
    bubble_growth_savings,
    heatmap_correlation,
    heatmap_industry_savings,
    technique_graph_spec,
    treemap_technique_frequency,
)
from storage_advisor.kb.loader import discover_families

PARQUET = None


@pytest.fixture(scope="module", autouse=True)
def _generate_parquet(tmp_path_factory):
    global PARQUET
    out = tmp_path_factory.mktemp("insights")
    gen = ScenarioGenerator()
    PARQUET = gen.generate(n=100, seed=42, output_dir=str(out))


class TestTreemap:
    def test_serializes_to_json(self):
        spec = treemap_technique_frequency(PARQUET)
        data = json.loads(spec)
        assert "data" in data

    def test_both_themes(self):
        for dark in (True, False):
            spec = treemap_technique_frequency(PARQUET, dark=dark)
            assert json.loads(spec)


class TestIndustryHeatmap:
    def test_serializes_to_json(self):
        spec = heatmap_industry_savings(PARQUET)
        data = json.loads(spec)
        assert "data" in data

    def test_both_themes(self):
        for dark in (True, False):
            spec = heatmap_industry_savings(PARQUET, dark=dark)
            assert json.loads(spec)


class TestCorrelation:
    def test_serializes_to_json(self):
        spec = heatmap_correlation(PARQUET)
        data = json.loads(spec)
        assert "data" in data


class TestBubble:
    def test_serializes_to_json(self):
        spec = bubble_growth_savings(PARQUET)
        data = json.loads(spec)
        assert "data" in data


class TestTechniqueGraph:
    def test_serializes_to_json(self):
        spec = technique_graph_spec()
        data = json.loads(spec)
        assert "data" in data

    def test_node_count_equals_family_count(self):
        families = discover_families()
        spec = technique_graph_spec()
        data = json.loads(spec)
        node_trace = data["data"][-1]
        node_count = len(node_trace["x"])
        assert node_count == len(families)


class TestAllFigures:
    def test_returns_all_keys(self):
        figs = all_figures(PARQUET)
        for key in ("treemap", "industry_heatmap", "correlation", "bubble", "graph"):
            assert key in figs
            assert json.loads(figs[key])
