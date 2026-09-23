"""Report exporters — Markdown and PDF renderers for ReportPayload."""

from __future__ import annotations

from storage_advisor.reports.builder import ReportPayload


def render_markdown(payload: ReportPayload) -> str:
    """Render a ReportPayload as a Markdown document."""
    sections: list[str] = []

    sections.append("# AI Data Architect — Consultant Report\n")

    sections.append("## Executive Summary\n")
    sections.append(payload.executive_summary + "\n")

    sections.append("## Architecture Overview\n")
    sections.append(payload.architecture_overview + "\n")

    sections.append("## Storage Strategy\n")
    for item in payload.storage_strategy:
        sections.append(
            f"- **{item['data_class']}**: {item['placement']}"
            + (f" (priority: {item['priority']})" if item.get("priority") else "")
        )
    sections.append("")

    sections.append("## Recommended Techniques\n")
    sections.append("| # | Technique | Priority | Alignment | Complexity |")
    sections.append("|---|-----------|----------|-----------|------------|")
    for i, rec in enumerate(payload.recommended_techniques, 1):
        sections.append(
            f"| {i} | {rec['technique_name']} | {rec['priority']} "
            f"| {rec['alignment_score']:.2f} | {rec['complexity']} |"
        )
    sections.append("")

    sections.append("## Implementation Roadmap\n")
    current_phase = -1
    for step in payload.implementation_roadmap:
        if step.phase != current_phase:
            current_phase = step.phase
            sections.append(f"### Phase {step.phase}: {step.phase_label}\n")
        sections.append(
            f"- **{step.technique_name}** — effort: {step.effort_estimate} "
            f"({step.effort_band})\n  Acceptance: {step.acceptance_criteria}"
        )
    sections.append("")

    sections.append("## Risk Analysis\n")
    for risk in payload.risk_analysis:
        status = "Addressed" if risk.addressed else "UNADDRESSED"
        sections.append(f"- [{status}] **{risk.name}** ({risk.severity})")
    sections.append("")

    sections.append("## Trade-offs\n")
    for t in payload.trade_offs:
        sections.append(f"- **{t.technique_id}**: {t.trade_off}")
    sections.append("")

    sections.append("## Scalability Analysis\n")
    sections.append(payload.scalability_analysis + "\n")
    if payload.scalability_points:
        for sp in payload.scalability_points:
            sections.append(f"- Month {sp.month}: {sp.trigger} — {sp.description}")
        sections.append("")

    sections.append("## Alternatives\n")
    for alt in payload.alternatives:
        sections.append(
            f"- **{alt['label']}** ({alt['focus']}): "
            f"{alt.get('trade_off', 'N/A')} "
            f"({alt['technique_count']} techniques)"
        )
    sections.append("")

    sections.append("---\n")
    sections.append(f"*{payload.impact_disclaimer}*\n")

    return "\n".join(sections)


def _latin1_safe(text: str) -> str:
    """Replace unicode characters unsupported by built-in PDF fonts."""
    return (
        text.replace("—", "--")
        .replace("–", "-")
        .replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("…", "...")
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )


def render_pdf(payload: ReportPayload) -> bytes:
    """Render a ReportPayload as a PDF document."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(
        0, 10, _latin1_safe("AI Data Architect - Consultant Report"),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(5)

    def _heading(text: str) -> None:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, _latin1_safe(text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    def _body(text: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _latin1_safe(text))
        pdf.ln(2)

    _heading("Executive Summary")
    _body(payload.executive_summary)

    _heading("Architecture Overview")
    _body(payload.architecture_overview)

    _heading("Storage Strategy")
    for item in payload.storage_strategy:
        _body(f"  {item['data_class']}: {item['placement']}")

    _heading("Recommended Techniques")
    for i, rec in enumerate(payload.recommended_techniques, 1):
        _body(
            f"  {i}. {rec['technique_name']} "
            f"(priority: {rec['priority']}, "
            f"alignment: {rec['alignment_score']:.2f}, "
            f"complexity: {rec['complexity']})"
        )

    _heading("Implementation Roadmap")
    current_phase = -1
    for step in payload.implementation_roadmap:
        if step.phase != current_phase:
            current_phase = step.phase
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(
                0, 7,
                _latin1_safe(f"Phase {step.phase}: {step.phase_label}"),
                new_x="LMARGIN", new_y="NEXT",
            )
            pdf.ln(1)
        _body(
            f"  {step.technique_name} - effort: {step.effort_estimate} "
            f"({step.effort_band})"
        )

    _heading("Risk Analysis")
    for risk in payload.risk_analysis:
        status = "Addressed" if risk.addressed else "UNADDRESSED"
        _body(f"  [{status}] {risk.name} ({risk.severity})")

    _heading("Trade-offs")
    for t in payload.trade_offs:
        _body(f"  {t.technique_id}: {t.trade_off}")

    _heading("Scalability Analysis")
    _body(payload.scalability_analysis)

    _heading("Alternatives")
    for alt in payload.alternatives:
        _body(
            f"  {alt['label']} ({alt['focus']}): "
            f"{alt.get('trade_off', 'N/A')}"
        )

    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, _latin1_safe(payload.impact_disclaimer))

    return pdf.output()
