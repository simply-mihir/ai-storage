"""Tests for the architecture story generator."""

from __future__ import annotations

import pytest

from storage_advisor.analytics.trajectory import GrowthTrajectorySimulator
from storage_advisor.architecture.builder import ArchitectureBuilder
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.export.story import ArchitectureStoryGenerator
from storage_advisor.recommendation.recommendation_engine import run_recommendation_engine


def _demo_scenario() -> Scenario:
    return Scenario(
        business_domain="E_COMMERCE",
        company_size="LARGE",
        expected_users=10_000_000,
        concurrent_users=500_000,
        current_storage_gb=5000,
        daily_growth_gb=300,
        data_types=["IMAGES", "TRANSACTIONS"],
        structured_data_pct=40,
        semi_structured_data_pct=10,
        unstructured_data_pct=50,
        read_intensity="HIGH",
        write_intensity="HIGH",
        access_pattern="MIXED",
        latency_requirement_ms=100,
        availability_requirement=99.99,
        rto_minutes=15,
        rpo_minutes=5,
        retention_years=7,
        budget_level="HIGH",
        analytics_required=True,
        real_time_processing_required=True,
        sensitive_data=True,
        encryption_required=True,
        compliance_requirements=["SOC2", "PCI_DSS"],
    )


@pytest.fixture
def story():
    scenario = _demo_scenario()
    result = run_recommendation_engine(scenario)
    impact = estimate_impact(scenario, result.recommendations)
    architecture = ArchitectureBuilder().build(scenario, result)
    gen = ArchitectureStoryGenerator()
    return gen.generate(scenario, result, impact, architecture)


class TestArchitectureStory:
    def test_story_generates_without_error(self, story):
        assert story.full_document != ""
        assert story.word_count > 200

    def test_all_six_sections_present(self, story):
        assert "## Context" in story.full_document
        assert "## Key Architectural Decisions" in story.full_document
        assert "## What We Explicitly Rejected" in story.full_document
        assert "## Top 3 Risks" in story.full_document
        assert "## 90-Day Implementation Sequence" in story.full_document
        assert "## Open Questions" in story.full_document

    def test_scenario_values_appear_in_document(self, story):
        doc = story.full_document
        assert "10,000,000" in doc or "10000000" in doc
        assert "100" in doc  # latency_requirement_ms

    def test_required_techniques_in_decisions(self, story):
        scenario = _demo_scenario()
        result = run_recommendation_engine(scenario)
        required = [
            r.technique_id.replace("_", " ").title()
            for r in result.recommendations
            if r.priority == "REQUIRED"
        ]
        for t in required:
            assert t in story.full_document, f"Missing required technique: {t}"

    def test_source_is_structured_engine(self, story):
        assert story.source == "structured_engine"

    def test_sections_dict_has_six_keys(self, story):
        assert len(story.sections) == 6
        assert "Context" in story.sections
        assert "Open Questions" in story.sections


class TestStoryWithTrajectory:
    def test_with_trajectory(self):
        scenario = _demo_scenario()
        result = run_recommendation_engine(scenario)
        impact = estimate_impact(scenario, result.recommendations)
        architecture = ArchitectureBuilder().build(scenario, result)
        trajectory = GrowthTrajectorySimulator().simulate(scenario, months=12)
        gen = ArchitectureStoryGenerator()
        story = gen.generate(
            scenario, result, impact, architecture, trajectory=trajectory,
        )
        doc = story.full_document.lower()
        assert "tipping point" in doc or "month" in doc
        assert "cost trajectory" in doc
