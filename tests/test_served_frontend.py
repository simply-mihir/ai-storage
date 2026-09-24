"""Served-bytes guard — asserts the HTML returned by GET / matches the canonical file.

This test catches the drift-from-editing problem: if the served response
ever diverges from static/index.html (wrong path, stale copy, caching),
these assertions fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from storage_advisor.app.api import app

CANONICAL = Path(__file__).resolve().parent.parent / "static" / "index.html"

client = TestClient(app)


@pytest.fixture(scope="module")
def served_html() -> str:
    resp = client.get("/")
    assert resp.status_code == 200, f"GET / returned {resp.status_code}"
    return resp.text


@pytest.fixture(scope="module")
def canonical_html() -> str:
    return CANONICAL.read_text(encoding="utf-8")


REQUIRED_MARKERS = [
    "empty-state-recommendations",
    "empty-state-impact",
    "empty-state-real-cost",
    "empty-state-explainability",
    "empty-state-growth",
    "empty-state-what-if",
    "last-analysis-chip",
    "export-report-btn",
    "arch-reset-btn",
]


@pytest.mark.parametrize("marker", REQUIRED_MARKERS)
def test_served_html_contains_marker(served_html: str, marker: str) -> None:
    assert marker in served_html, (
        f"GET / response missing '{marker}' — served HTML has drifted from canonical file"
    )


STALE_PATTERNS = [
    'value="25000"',
    'value="3500"',
    'value="12000"',
    'value="8500"',
    'value="AI SaaS"',
    'value="85"',
    'value="45"',
    'value="36"',
]


@pytest.mark.parametrize("pattern", STALE_PATTERNS)
def test_served_html_no_stale_prefill(served_html: str, pattern: str) -> None:
    assert pattern not in served_html, (
        f"GET / response still contains stale prefill '{pattern}'"
    )


def test_served_matches_canonical(served_html: str, canonical_html: str) -> None:
    assert served_html == canonical_html, (
        "GET / response differs from static/index.html — serving a stale or wrong copy"
    )


def test_cache_control_header() -> None:
    resp = client.get("/")
    cc = resp.headers.get("cache-control", "")
    assert "no-cache" in cc or "no-store" in cc, (
        f"GET / Cache-Control header should contain no-cache or no-store, got: '{cc}'"
    )
