"""Frontend contract guard — asserts required UI elements exist in index.html.

If a future commit removes a required element, the assertion names
the missing id so the engineer knows exactly what was deleted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"


@pytest.fixture(scope="module")
def html() -> str:
    return INDEX.read_text(encoding="utf-8")


# -- Report surface (Sprint A) -----------------------------------------------

def test_export_report_btn(html: str) -> None:
    assert 'id="export-report-btn"' in html, "Missing id='export-report-btn' (Export Report pill)"


def test_report_preview_well(html: str) -> None:
    assert 'id="report-preview-well"' in html, "Missing id='report-preview-well' (Report Preview inset well)"


def test_advisory_pending_marker(html: str) -> None:
    assert "Advisory pending knowledge cutover" in html, (
        "Missing 'Advisory pending knowledge cutover' marker string in Explainability tab"
    )


# -- Insights tab (Sprint B) -------------------------------------------------

INSIGHT_PLOT_IDS = [
    "plot-treemap",
    "plot-industry-heatmap",
    "plot-correlation",
    "plot-bubble",
    "plot-technique-graph",
]


@pytest.mark.parametrize("plot_id", INSIGHT_PLOT_IDS)
def test_insight_plot_container(html: str, plot_id: str) -> None:
    assert f'id="{plot_id}"' in html, f"Missing id='{plot_id}' (Insights tab plot container)"


# -- Second opinion (Sprint C) -----------------------------------------------

def test_second_opinion_card(html: str) -> None:
    assert 'id="second-opinion-card"' in html, "Missing id='second-opinion-card' (Second Opinion card)"


# -- Theme toggle (cross-cutting X1) ------------------------------------------

def test_theme_toggle_homepage(html: str) -> None:
    assert 'class="circle-btn theme-toggle-btn"' in html, (
        "Missing theme-toggle-btn class (theme toggle button)"
    )


def test_theme_toggle_function(html: str) -> None:
    assert "function toggleTheme()" in html, "Missing toggleTheme() function definition"


def test_theme_toggle_listeners(html: str) -> None:
    assert "theme-toggle-btn" in html, "Missing theme-toggle-btn event listener wiring"


def test_two_theme_toggle_buttons(html: str) -> None:
    count = html.count('class="circle-btn theme-toggle-btn"')
    assert count >= 2, (
        f"Expected theme toggle in both homepage and dashboard, found {count} instance(s)"
    )
