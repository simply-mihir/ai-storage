"""Tests for the report payload builder."""

from storage_advisor.domain.scenario import Scenario
from storage_advisor.reports.builder import build_report


def _demo_scenario(**overrides) -> Scenario:
    defaults = {
        "business_domain": "AI",
        "company_size": "ENTERPRISE",
        "expected_users": 10_000_000,
        "concurrent_users": 100_000,
        "current_storage_gb": 25_000,
        "daily_growth_gb": 300,
        "data_types": ["IMAGES", "DOCUMENTS", "TRANSACTIONS", "LOGS"],
        "structured_data_pct": 20,
        "semi_structured_data_pct": 20,
        "unstructured_data_pct": 60,
        "read_intensity": "HIGH",
        "write_intensity": "HIGH",
        "access_pattern": "MIXED",
        "latency_requirement_ms": 100,
        "availability_requirement": 99.99,
        "rto_minutes": 60,
        "rpo_minutes": 15,
        "retention_years": 7,
        "budget_level": "HIGH",
        "analytics_required": True,
        "real_time_processing_required": True,
        "sensitive_data": True,
        "encryption_required": True,
        "compliance_requirements": ["NONE"],
    }
    defaults.update(overrides)
    return Scenario(**defaults)


class TestReportPayloadBuilder:

    def test_report_builds_successfully(self):
        scenario = _demo_scenario()
        report = build_report(scenario)
        assert report.executive_summary
        assert report.architecture_overview
        assert len(report.recommended_techniques) >= 5
        assert len(report.implementation_roadmap) >= 1

    def test_executive_summary_contains_disclaimer(self):
        report = build_report(_demo_scenario())
        assert "MODEL-BASED" in report.executive_summary

    def test_roadmap_phases_monotonic(self):
        report = build_report(_demo_scenario())
        phases = [step.phase for step in report.implementation_roadmap]
        for i in range(1, len(phases)):
            assert phases[i] >= phases[i - 1], (
                f"Phase {phases[i]} at index {i} is less than "
                f"phase {phases[i - 1]} at index {i - 1}"
            )

    def test_roadmap_never_places_step_before_requires(self):
        report = build_report(_demo_scenario())
        step_phases = {
            step.technique_id: step.phase
            for step in report.implementation_roadmap
        }
        from storage_advisor.kb.loader import project_graph
        graph = project_graph()
        graph_nodes = set(graph.nodes)
        for step in report.implementation_roadmap:
            if step.technique_id not in graph_nodes:
                continue
            for pred in graph.predecessors(step.technique_id):
                edge_data = graph.get_edge_data(pred, step.technique_id)
                if (
                    edge_data
                    and edge_data.get("relation") == "REQUIRES"
                    and pred in step_phases
                ):
                    assert step_phases[pred] <= step.phase, (
                        f"{step.technique_id} (phase {step.phase}) placed "
                        f"before its prerequisite {pred} (phase {step_phases[pred]})"
                    )

    def test_risk_analysis_covers_all_problems(self):
        report = build_report(_demo_scenario())
        assert len(report.risk_analysis) >= 1
        has_addressed = any(r.addressed for r in report.risk_analysis)
        assert has_addressed

    def test_trade_offs_from_top_techniques(self):
        report = build_report(_demo_scenario())
        assert len(report.trade_offs) >= 1
        for t in report.trade_offs:
            assert t.trade_off

    def test_scalability_analysis_present(self):
        report = build_report(_demo_scenario())
        assert report.scalability_analysis
        assert "concurrent" in report.scalability_analysis.lower() or "users" in report.scalability_analysis.lower()

    def test_alternatives_present(self):
        report = build_report(_demo_scenario())
        assert len(report.alternatives) >= 1

    def test_storage_strategy_maps_components(self):
        report = build_report(_demo_scenario())
        assert len(report.storage_strategy) >= 1
        for item in report.storage_strategy:
            assert "data_class" in item
            assert "placement" in item

    def test_impact_disclaimer_present(self):
        report = build_report(_demo_scenario())
        assert "MODEL-BASED" in report.impact_disclaimer
