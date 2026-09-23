"""Unit tests for case study literature validation and alignment scorer."""

from __future__ import annotations

from scripts.case_study import (
    compute_alignment,
    evaluate_case_study,
    format_alignment_markdown,
    get_netflix_documented_choices,
    get_netflix_scenario,
    get_uber_documented_choices,
    get_uber_scenario,
)


class TestAlignmentScorer:
    def test_compute_alignment_all_matched(self):
        documented = [
            {"technique_id": "caching", "technique_name": "Caching"},
            {"technique_id": "sharding", "technique_name": "Sharding"},
        ]
        recs = ["caching", "sharding", "replication"]
        result = compute_alignment(recs, documented)
        assert result["score"] == 1.0
        assert result["alignment_pct"] == 100.0
        assert result["matched_count"] == 2
        assert len(result["unmatched"]) == 0

    def test_compute_alignment_partial_match(self):
        documented = [
            {"technique_id": "caching", "technique_name": "Caching"},
            {"technique_id": "sharding", "technique_name": "Sharding"},
            {"technique_id": "compression", "technique_name": "Compression"},
            {"technique_id": "indexing", "technique_name": "Indexing"},
        ]
        recs = ["caching", "sharding"]
        result = compute_alignment(recs, documented)
        assert result["score"] == 0.5
        assert result["alignment_pct"] == 50.0
        assert result["matched_count"] == 2
        assert len(result["unmatched"]) == 2

    def test_compute_alignment_empty(self):
        result = compute_alignment([], [])
        assert result["score"] == 0.0
        assert result["alignment_pct"] == 0.0


class TestNetflixCaseStudy:
    def test_netflix_scenario_valid(self):
        sc = get_netflix_scenario()
        assert sc.business_domain == "MEDIA"
        assert sc.current_storage_gb == 500_000.0
        assert sc.unstructured_data_pct == 70.0

    def test_netflix_documented_choices_citations(self):
        choices = get_netflix_documented_choices()
        assert len(choices) >= 5
        for c in choices:
            assert c["citation_url"].startswith("https://")
            assert len(c["citation_title"]) > 5
            assert len(c["context"]) > 10

    def test_netflix_evaluation_alignment(self):
        res = evaluate_case_study("netflix")
        assert res["alignment"]["score"] >= 0.80
        assert res["alignment"]["alignment_pct"] >= 80.0
        assert len(res["mismatches"]) >= 2
        assert any("Cassandra" in m["company_reality"] for m in res["mismatches"])


class TestUberCaseStudy:
    def test_uber_scenario_valid(self):
        sc = get_uber_scenario()
        assert sc.business_domain == "LOGISTICS"
        assert sc.write_intensity == "HIGH"
        assert "GPS_DATA" in sc.data_types

    def test_uber_documented_choices_citations(self):
        choices = get_uber_documented_choices()
        assert len(choices) >= 5
        for c in choices:
            assert c["citation_url"].startswith("https://")
            assert len(c["citation_title"]) > 5
            assert len(c["context"]) > 10

    def test_uber_evaluation_alignment(self):
        res = evaluate_case_study("uber")
        assert res["alignment"]["score"] >= 0.80
        assert res["alignment"]["alignment_pct"] >= 80.0
        assert len(res["mismatches"]) >= 2
        assert any("Schemaless" in m["company_reality"] for m in res["mismatches"])

    def test_format_alignment_markdown(self):
        res = evaluate_case_study("uber")
        md = format_alignment_markdown(res)
        assert "| Recommended Technique |" in md
        assert "Honest Mismatches" in md
        assert "https://" in md
