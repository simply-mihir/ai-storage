"""Tests for report exporters and API endpoints."""

from fastapi.testclient import TestClient

from storage_advisor.app.api import app
from storage_advisor.domain.scenario import Scenario
from storage_advisor.reports.builder import build_report
from storage_advisor.reports.export import render_markdown, render_pdf

client = TestClient(app)

DEMO_SCENARIO = {
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


def _payload():
    scenario = Scenario(**DEMO_SCENARIO)
    return build_report(scenario)


class TestMarkdownExporter:

    def test_md_contains_all_section_headings(self):
        md = render_markdown(_payload())
        assert "## Executive Summary" in md
        assert "## Architecture Overview" in md
        assert "## Storage Strategy" in md
        assert "## Recommended Techniques" in md
        assert "## Implementation Roadmap" in md
        assert "## Risk Analysis" in md
        assert "## Trade-offs" in md
        assert "## Scalability Analysis" in md
        assert "## Alternatives" in md

    def test_md_contains_disclaimer(self):
        md = render_markdown(_payload())
        assert "MODEL-BASED" in md

    def test_md_contains_roadmap_phases(self):
        md = render_markdown(_payload())
        assert "Phase 0" in md or "Phase 1" in md


class TestPdfExporter:

    def test_pdf_starts_with_header(self):
        pdf_bytes = render_pdf(_payload())
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_is_nonempty(self):
        pdf_bytes = render_pdf(_payload())
        assert len(pdf_bytes) > 1000


class TestReportEndpoints:

    def test_post_report_returns_payload(self):
        resp = client.post("/api/v1/report", json={"scenario": DEMO_SCENARIO})
        assert resp.status_code == 200
        data = resp.json()
        assert "executive_summary" in data
        assert "implementation_roadmap" in data
        assert "MODEL-BASED" in data["executive_summary"]

    def test_post_report_invalid_scenario(self):
        resp = client.post("/api/v1/report", json={"scenario": {"bad": "data"}})
        assert resp.status_code == 400

    def test_get_export_md(self):
        resp = client.get("/api/v1/report/export?format=md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "md"
        assert "## Executive Summary" in data["data"]

    def test_get_export_pdf(self):
        resp = client.get("/api/v1/report/export?format=pdf")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "pdf"
        pdf_bytes = bytes.fromhex(data["data"])
        assert pdf_bytes[:5] == b"%PDF-"

    def test_endpoint_auth_free_parity(self):
        resp_md = client.get("/api/v1/report/export?format=md")
        resp_pdf = client.get("/api/v1/report/export?format=pdf")
        assert resp_md.status_code == 200
        assert resp_pdf.status_code == 200
