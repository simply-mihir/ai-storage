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


# -- Trust defect: empty-first form (Sprint D) ---------------------------------

FORM_INPUTS_NO_VALUE = [
    "f-domain",
    "f-users",
    "f-concurrent",
    "f-storage",
    "f-growth",
    "f-latency",
    "f-retention",
    "f-budget",
]


@pytest.mark.parametrize("input_id", FORM_INPUTS_NO_VALUE)
def test_no_hardcoded_value_attribute(html: str, input_id: str) -> None:
    """Form inputs must not ship with a hardcoded value= attribute."""
    import re

    pattern = rf'id="{input_id}"[^>]*\bvalue="[^"]*"'
    assert not re.search(pattern, html), (
        f"Input '{input_id}' still has a hardcoded value attribute"
    )


def test_selects_have_disabled_placeholder(html: str) -> None:
    """Both select elements must have a disabled placeholder first option."""
    assert 'value="" disabled selected' in html, (
        "Missing disabled placeholder option in select elements"
    )


EMPTY_STATE_IDS = [
    "empty-state-recommendations",
    "empty-state-impact",
    "empty-state-real-cost",
    "empty-state-explainability",
    "empty-state-growth",
    "empty-state-what-if",
]


@pytest.mark.parametrize("es_id", EMPTY_STATE_IDS)
def test_empty_state_container(html: str, es_id: str) -> None:
    """Each results tab must have an empty-state placeholder."""
    assert f'id="{es_id}"' in html, f"Missing id='{es_id}' (empty-state container)"


def test_results_tab_class(html: str) -> None:
    """All 6 results panels must carry the results-tab class."""
    for panel in ["recommendations", "impact", "real-cost", "explainability", "growth", "what-if"]:
        assert f'results-tab" id="panel-{panel}"' in html, (
            f"panel-{panel} missing results-tab class"
        )


def test_validate_architect_form_function(html: str) -> None:
    assert "function validateArchitectForm()" in html, (
        "Missing validateArchitectForm() function"
    )


def test_sync_form_to_state_function(html: str) -> None:
    assert "function syncFormToState()" in html, (
        "Missing syncFormToState() function"
    )


def test_clear_architect_form_function(html: str) -> None:
    assert "function clearArchitectForm()" in html, (
        "Missing clearArchitectForm() function"
    )


def test_clear_form_button(html: str) -> None:
    assert 'id="arch-reset-btn"' in html, "Missing Clear Form button"
    assert "Clear Form" in html, "Button should read 'Clear Form'"


def test_no_auto_load_second_opinion(html: str) -> None:
    """The auto-load fetchSecondOpinion('ai-saas') call must be removed."""
    assert "// Initial load" not in html, (
        "Auto-load comment '// Initial load' still present — fetchSecondOpinion auto-load should be removed"
    )


def test_no_auto_load_report_preview(html: str) -> None:
    """loadReportPreview() must not be called at module scope."""
    import re

    hits = re.findall(r"^\s*loadReportPreview\(\)", html, re.MULTILINE)
    assert len(hits) == 0, (
        "Found top-level loadReportPreview() call — auto-load should be removed"
    )


def test_last_analysis_chip(html: str) -> None:
    assert 'id="last-analysis-chip"' in html, "Missing last-analysis-chip element"


def test_default_active_tab_is_architect(html: str) -> None:
    """Dashboard should open on the Architect tab, not Recommendations."""
    assert 'class="dash-tab-panel active" id="panel-architect"' in html, (
        "panel-architect should have the active class by default"
    )


# -- Removed elements regression guard -----------------------------------------

REMOVED_STRINGS = [
    "hero-pill-badge",
    "hero-badge-wrap",
    "Deterministic Core",
    "credibility-section",
    "cred-pill",
    "pytest 222",
]


@pytest.mark.parametrize("removed", REMOVED_STRINGS)
def test_removed_elements_stay_removed(html: str, removed: str) -> None:
    assert removed not in html, f"Removed element '{removed}' has regressed back into the markup"
