"""Streamlit UI for AI Data Architect — storage architecture advisor."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from storage_advisor.analytics.charts import all_charts
from storage_advisor.analytics.store import AnalyticsStore
from storage_advisor.analytics.whatif import WhatIfAnalyzer
from storage_advisor.architecture.builder import ArchitectureBuilder
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.integrations.bedrock import BedrockExplainer
from storage_advisor.integrations.pricing import AWSPricingClient
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.recommendation.recommendation_engine import run_recommendation_engine

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit command
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AI Data Architect", page_icon="\U0001f3d7️", layout="wide")

# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------

@st.cache_resource
def _load_engine():
    techniques = load_techniques()
    try:
        store = AnalyticsStore("data/synthetic/scenarios.parquet")
    except Exception:
        store = None
    return {
        "techniques": techniques,
        "builder": ArchitectureBuilder(),
        "whatif": WhatIfAnalyzer(),
        "bedrock": BedrockExplainer(),
        "pricing": AWSPricingClient(),
        "store": store,
    }


@st.cache_resource
def _load_charts(_store):
    return all_charts(_store)


@st.cache_resource
def _load_ml():
    from storage_advisor.analytics.ml_experiment import run_experiment
    return run_experiment()


components = _load_engine()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DOMAIN_OPTIONS = [
    "AI", "FINTECH", "HEALTHCARE", "MEDIA",
    "GAMING", "SAAS", "IOT", "ECOMMERCE",
]

_DATA_TYPE_OPTIONS = [
    "TRANSACTIONS", "IMAGES", "VIDEOS", "DOCUMENTS",
    "TIME_SERIES", "LOGS", "TEXT", "SENSOR_DATA",
    "CLICKSTREAM", "EMBEDDINGS",
]

_COMPLIANCE_OPTIONS = ["HIPAA", "PCI_DSS", "GDPR", "SOC2"]

_BUDGET_MAP = {"startup": "LOW", "growth": "MEDIUM", "enterprise": "HIGH"}
_SIZE_MAP = {"startup": "STARTUP", "growth": "MEDIUM", "enterprise": "ENTERPRISE"}

_STRUCTURED = {"TRANSACTIONS", "TIME_SERIES", "TEXT", "CLICKSTREAM"}
_SEMI = {"LOGS", "DOCUMENTS", "SENSOR_DATA", "EMBEDDINGS", "ML_FEATURES"}
_UNSTRUCTURED = {"IMAGES", "VIDEOS", "AUDIO"}

_RTO_RPO = {
    99.999: (5, 1),
    99.99: (30, 5),
    99.9: (60, 15),
    99.5: (120, 30),
    99.0: (240, 120),
}


def _infer_pcts(data_types: list[str]) -> tuple[float, float, float]:
    s = sum(1 for d in data_types if d in _STRUCTURED)
    sm = sum(1 for d in data_types if d in _SEMI)
    u = sum(1 for d in data_types if d in _UNSTRUCTURED)
    total = s + sm + u
    if total == 0:
        return 50.0, 30.0, 20.0
    sp = round(s / total * 100)
    smp = round(sm / total * 100)
    return float(sp), float(smp), float(100 - sp - smp)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("AI Data Architect")
st.sidebar.caption("Storage architecture advisor — 3-day hackathon MVP")

if components["bedrock"].available:
    st.sidebar.success("AI explanations: active")
else:
    st.sidebar.warning("AI explanations: unavailable (structured mode)")

st.sidebar.divider()
st.sidebar.markdown(
    "**How it works:**\n"
    "1. Describe your workload\n"
    "2. Review recommendations\n"
    "3. Explore impact estimates\n"
    "4. Run what-if scenarios"
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
for _k in [
    "current_scenario", "current_result", "current_impact",
    "current_architecture", "current_explanation",
]:
    if _k not in st.session_state:
        st.session_state[_k] = None

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_arch, tab_rec, tab_impact, tab_cost, tab_growth, tab_why, tab_analytics, tab_whatif = st.tabs([
    "\U0001f3d7️ Architect",
    "\U0001f4cb Recommendation",
    "\U0001f4ca Impact",
    "\U0001f4b0 Real Cost",
    "\U0001f4c8 Growth Roadmap",
    "❓ Why?",
    "\U0001f4c8 Analytics",
    "\U0001f504 What-if",
])


# ===================================================================
# TAB 1 — Architect
# ===================================================================
with tab_arch:
    # --- Section A: NL input ---
    st.subheader("Describe your workload")
    nl_input = st.text_area(
        "Describe in plain English…",
        placeholder=(
            "e.g. We're an AI startup with 10M users, storing 300 GB/day "
            "of images and transactional data. We need <100ms latency, "
            "99.99% availability, 7-year retention."
        ),
    )
    if st.button("Extract fields from description") and nl_input:
        with st.spinner("Extracting…"):
            extracted = components["bedrock"].extract_scenario_from_text(nl_input)
        if extracted:
            st.session_state["extracted_fields"] = extracted
            st.success("Fields extracted — review and adjust below.")
        else:
            st.warning(
                "Could not extract fields (Bedrock unavailable). "
                "Please fill the form manually."
            )

    if st.session_state.get("extracted_fields"):
        with st.expander("Extracted fields (preview)", expanded=True):
            st.json(st.session_state["extracted_fields"])

    st.divider()

    # --- Section B: Structured form ---
    st.subheader("Configure your scenario")

    col1, col2 = st.columns(2)

    with col1:
        business_domain = st.selectbox("Business domain", _DOMAIN_OPTIONS, index=0)
        users = st.number_input(
            "Expected users", min_value=1, value=10_000_000, step=100_000,
        )
        storage_gb = st.number_input("Current storage (GB)", min_value=1, value=25_000)
        daily_growth = st.number_input("Daily growth (GB/day)", min_value=0, value=300)
        data_types = st.multiselect(
            "Data types", _DATA_TYPE_OPTIONS, default=["TRANSACTIONS", "IMAGES"],
        )

    with col2:
        read_intensity = st.select_slider(
            "Read intensity", ["LOW", "MEDIUM", "HIGH"], value="HIGH",
        )
        write_intensity = st.select_slider(
            "Write intensity", ["LOW", "MEDIUM", "HIGH"], value="HIGH",
        )
        latency_ms = st.number_input("Latency target (ms)", min_value=1, value=100)
        availability = st.select_slider(
            "Availability",
            [99.0, 99.5, 99.9, 99.99, 99.999],
            value=99.99,
            format_func=lambda x: f"{x}%",
        )
        retention_years = st.number_input("Retention (years)", min_value=0, value=7)

    # Row 2 — full width
    compliance = st.multiselect("Compliance requirements", _COMPLIANCE_OPTIONS)
    col_a, col_b = st.columns(2)
    with col_a:
        analytics_flag = st.checkbox("Analytics / ML workload", value=True)
    with col_b:
        budget_tier = st.selectbox(
            "Budget tier", ["startup", "growth", "enterprise"], index=1,
        )

    # Analyze button
    if st.button(
        "\U0001f50d Analyze Architecture", type="primary", use_container_width=True,
    ):
        if not data_types:
            st.error("Please select at least one data type.")
        else:
            with st.spinner("Running analysis…"):
                try:
                    struct_pct, semi_pct, unstruct_pct = _infer_pcts(data_types)
                    rto, rpo = _RTO_RPO.get(availability, (60, 15))
                    concurrent = max(1, users // 10)
                    has_compliance = len(compliance) > 0

                    scenario = Scenario(
                        business_domain=business_domain,
                        company_size=_SIZE_MAP[budget_tier],
                        expected_users=users,
                        concurrent_users=concurrent,
                        current_storage_gb=float(storage_gb),
                        daily_growth_gb=float(daily_growth),
                        data_types=data_types,
                        structured_data_pct=struct_pct,
                        semi_structured_data_pct=semi_pct,
                        unstructured_data_pct=unstruct_pct,
                        read_intensity=read_intensity,
                        write_intensity=write_intensity,
                        access_pattern="MIXED",
                        latency_requirement_ms=float(latency_ms),
                        availability_requirement=availability,
                        rto_minutes=float(rto),
                        rpo_minutes=float(rpo),
                        retention_years=float(retention_years),
                        budget_level=_BUDGET_MAP[budget_tier],
                        analytics_required=analytics_flag,
                        real_time_processing_required=False,
                        sensitive_data=has_compliance,
                        encryption_required=has_compliance,
                        compliance_requirements=(
                            compliance if compliance else ["NONE"]
                        ),
                    )

                    result = run_recommendation_engine(
                        scenario, components["techniques"],
                    )
                    impact = estimate_impact(scenario, result.recommendations)
                    arch = components["builder"].build(scenario, result)
                    explanation = components["bedrock"].explain(
                        result, scenario, impact,
                    )

                    st.session_state.current_scenario = scenario
                    st.session_state.current_result = result
                    st.session_state.current_impact = impact
                    st.session_state.current_architecture = arch
                    st.session_state.current_explanation = explanation

                    st.success(
                        f"Analysis complete — {len(result.recommendations)} "
                        f"recommendations generated."
                    )
                    st.info(
                        "View results in the tabs: "
                        "Recommendation → Impact → Why? → What-if"
                    )
                except Exception as e:
                    st.error(f"Analysis failed: {e}")


# ===================================================================
# TAB 2 — Recommendation
# ===================================================================
with tab_rec:
    if st.session_state.current_result is None:
        st.info("Run analysis first (Architect tab).")
    else:
        arch = st.session_state.current_architecture
        result = st.session_state.current_result

        # Architecture summary
        st.subheader("Recommended architecture")
        st.caption(arch.summary)

        if arch.components:
            domain_groups: dict[str, list] = {}
            for comp in arch.components:
                domain_groups.setdefault(comp.workload_domain, []).append(comp)

            num_cols = min(len(domain_groups), 4)
            cols = st.columns(num_cols)
            for i, (domain, comps) in enumerate(domain_groups.items()):
                with cols[i % num_cols]:
                    st.markdown(f"**{domain.upper()}**")
                    for comp in comps:
                        badge = (
                            "\U0001f534 REQUIRED"
                            if comp.priority == "REQUIRED"
                            else "\U0001f7e1 RECOMMENDED"
                        )
                        with st.container(border=True):
                            st.markdown(f"**{comp.service}**")
                            st.caption(badge)
                            for note in comp.configuration_notes:
                                st.markdown(f"- {note}")
                            st.caption(
                                f"Required by: {', '.join(comp.required_by)}"
                            )

        st.divider()

        # Recommendations list
        st.subheader("Optimization techniques")
        sorted_recs = sorted(
            result.recommendations,
            key=lambda r: (
                0 if r.priority == "REQUIRED" else 1,
                -r.alignment_score,
            ),
        )
        for rec in sorted_recs:
            label = rec.technique_id.replace("_", " ").title()
            with st.expander(
                f"{label} [{rec.priority}] — score: {rec.alignment_score:.3f}"
            ):
                st.write(f"**Why:** {rec.rationale}")
                st.write(f"**Benefits:** {'; '.join(rec.benefits)}")
                st.write(f"**Trade-offs:** {'; '.join(rec.disadvantages)}")
                st.write(f"**Complexity:** {rec.implementation_complexity}")
                if rec.conditions:
                    st.write(
                        f"**Do not use when:** {'; '.join(rec.conditions)}"
                    )

        st.divider()

        # Alternatives
        st.subheader("Alternative strategies")
        for alt in result.alternatives:
            with st.expander(f"{alt.label} — {alt.focus}"):
                technique_ids = ", ".join(
                    t.technique_id for t in alt.techniques
                )
                st.write(f"**Techniques:** {technique_ids}")
                st.write(f"**Trade-off:** {alt.trade_off}")
                st.write(f"**Cost delta:** {alt.estimated_cost_delta}")

        st.divider()
        st.subheader("Export")

        _ex_col1, _ex_col2 = st.columns(2)

        with _ex_col1:
            if st.button(
                "Download Terraform scaffold",
                use_container_width=True,
                help="Download main.tf, variables.tf, outputs.tf as a zip",
            ):
                from storage_advisor.export.terraform import TerraformGenerator
                _tf_gen = TerraformGenerator()
                _tf_export = _tf_gen.generate(
                    st.session_state.current_scenario,
                    st.session_state.current_architecture,
                )
                st.download_button(
                    label=f"terraform-scaffold.zip ({_tf_export.resource_count} resources)",
                    data=_tf_export.zip_bytes,
                    file_name="terraform-scaffold.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
                st.caption(_tf_export.summary)

        with _ex_col2:
            if st.button(
                "Preview Terraform",
                use_container_width=True,
                help="Preview main.tf in the browser",
            ):
                from storage_advisor.export.terraform import TerraformGenerator
                _tf_gen = TerraformGenerator()
                _tf_export = _tf_gen.generate(
                    st.session_state.current_scenario,
                    st.session_state.current_architecture,
                )
                with st.expander("main.tf preview", expanded=True):
                    st.code(_tf_export.files["main.tf"], language="hcl")
                with st.expander("variables.tf"):
                    st.code(_tf_export.files["variables.tf"], language="hcl")
                with st.expander("outputs.tf"):
                    st.code(_tf_export.files["outputs.tf"], language="hcl")


# ===================================================================
# TAB 3 — Impact
# ===================================================================
with tab_impact:
    if st.session_state.current_impact is None:
        st.info("Run analysis first (Architect tab).")
    else:
        impact = st.session_state.current_impact

        st.caption(
            "⚠️ All figures are model-based estimates generated from "
            "documented assumptions. They are not empirical production measurements."
        )

        # KPI row
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Storage",
            f"{impact.storage.projected_storage_gb:,.0f} GB",
            delta=f"-{impact.storage.estimated_reduction_pct:.1f}%",
        )
        c2.metric(
            "Monthly cost",
            f"${impact.cost.estimated_monthly_optimized_usd:,.0f}",
            delta=f"-{impact.cost.estimated_savings_pct:.1f}%",
        )
        c3.metric(
            "Latency",
            f"{impact.latency.estimated_optimized_latency_ms:.0f}ms",
            delta=f"-{impact.latency.estimated_improvement_pct:.1f}%",
            delta_color="inverse",
        )

        st.divider()

        # Before / after bar charts
        bc1, bc2 = st.columns(2)
        with bc1:
            fig_s = go.Figure(data=[
                go.Bar(
                    name="Baseline",
                    x=["Storage (GB)"],
                    y=[impact.storage.current_storage_gb],
                    marker_color="#EF4444",
                ),
                go.Bar(
                    name="Optimized",
                    x=["Storage (GB)"],
                    y=[impact.storage.projected_storage_gb],
                    marker_color="#10B981",
                ),
            ])
            fig_s.update_layout(
                title="Storage: before vs after",
                barmode="group", height=350, yaxis_title="GB",
            )
            st.plotly_chart(fig_s, use_container_width=True)

        with bc2:
            fig_c = go.Figure(data=[
                go.Bar(
                    name="Baseline",
                    x=["Monthly cost ($)"],
                    y=[impact.cost.estimated_monthly_baseline_usd],
                    marker_color="#EF4444",
                ),
                go.Bar(
                    name="Optimized",
                    x=["Monthly cost ($)"],
                    y=[impact.cost.estimated_monthly_optimized_usd],
                    marker_color="#10B981",
                ),
            ])
            fig_c.update_layout(
                title="Cost: before vs after",
                barmode="group", height=350, yaxis_title="$/month",
            )
            st.plotly_chart(fig_c, use_container_width=True)

        # Assumptions
        with st.expander("Assumptions behind these estimates"):
            st.markdown("**Storage assumptions:**")
            for a in impact.storage.assumptions:
                st.write(f"- {a}")
            st.markdown("**Cost assumptions:**")
            for a in impact.cost.assumptions:
                st.write(f"- {a}")
            st.markdown("**Latency assumptions:**")
            for a in impact.latency.assumptions:
                st.write(f"- {a}")

        st.divider()
        st.subheader("Confidence ranges")
        st.caption(
            "Ranges show 25th–75th percentile outcomes from similar "
            "synthetic scenarios."
        )

        from storage_advisor.estimation.confidence import ConfidenceEstimator

        @st.cache_resource
        def _get_confidence_estimator():
            return ConfidenceEstimator()

        _conf = _get_confidence_estimator()
        _banded = _conf.estimate_with_bands(
            st.session_state.current_scenario, impact,
        )

        _fig_bands = go.Figure()
        for _bl, _bb in [
            ("Storage reduction %", _banded.storage_band),
            ("Cost reduction %", _banded.cost_band),
            ("Latency improvement %", _banded.latency_band),
        ]:
            _fig_bands.add_trace(go.Bar(
                name=_bl,
                x=[_bb.high - _bb.low],
                y=[_bl],
                base=[_bb.low],
                orientation="h",
                marker_color="#93C5FD",
                showlegend=False,
                hovertemplate=(
                    f"{_bl}<br>Range: {_bb.low:.1f}% – {_bb.high:.1f}%"
                    f"<br>Point estimate: {_bb.point_estimate:.1f}%"
                    "<extra></extra>"
                ),
            ))
            _fig_bands.add_trace(go.Scatter(
                x=[_bb.point_estimate],
                y=[_bl],
                mode="markers",
                marker=dict(color="#5B4FDC", size=12, symbol="diamond"),
                showlegend=False,
                hovertemplate=(
                    f"Point estimate: {_bb.point_estimate:.1f}%<extra></extra>"
                ),
            ))

        _fig_bands.update_layout(
            title="Expected outcome ranges (25th–75th percentile)",
            xaxis_title="Reduction / Improvement %",
            xaxis=dict(range=[0, 100]),
            height=250,
            margin=dict(l=20, r=20, t=40, b=20),
            barmode="overlay",
        )
        st.plotly_chart(_fig_bands, use_container_width=True)

        _bc1, _bc2, _bc3 = st.columns(3)
        _bc1.caption(f"Storage: {_banded.storage_band.confidence_note}")
        _bc2.caption(f"Cost: {_banded.cost_band.confidence_note}")
        _bc3.caption(f"Latency: {_banded.latency_band.confidence_note}")

        st.caption(_banded.disclaimer)


# ===================================================================
# TAB 4 — Real Cost
# ===================================================================
with tab_cost:
    if st.session_state.current_architecture is None:
        st.info("Run analysis first (Architect tab).")
    else:
        import pandas as pd
        from datetime import date as _date

        st.subheader("AWS list price breakdown")
        st.caption(
            f"Region: us-east-1 — Based on AWS public pricing as of "
            f"{_date.today().isoformat()}"
        )

        pricing_result = components["pricing"].calculate_monthly_architecture_cost(
            st.session_state.current_architecture,
            st.session_state.current_scenario,
        )

        st.metric(
            "Estimated monthly AWS cost",
            f"${pricing_result.total_monthly_usd:,.2f}",
            help="Based on AWS list prices. See disclaimer below.",
        )

        df_cost = pd.DataFrame([{
            "Service": item.service,
            "Description": item.label,
            "Monthly Cost": f"${item.monthly_cost_usd:,.2f}",
        } for item in pricing_result.line_items])
        st.dataframe(df_cost, use_container_width=True, hide_index=True)

        fig_cost = px.bar(
            x=[item.service for item in pricing_result.line_items],
            y=[item.monthly_cost_usd for item in pricing_result.line_items],
            labels={"x": "Service", "y": "Monthly Cost (USD)"},
            title="Monthly cost by AWS service",
            color=[item.monthly_cost_usd for item in pricing_result.line_items],
            color_continuous_scale="Blues",
        )
        st.plotly_chart(fig_cost, use_container_width=True)

        new_region = st.selectbox(
            "Compare pricing in another region",
            ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"],
            index=0,
        )
        if new_region != "us-east-1":
            alt_pricing = AWSPricingClient(region=new_region)
            alt_result = alt_pricing.calculate_monthly_architecture_cost(
                st.session_state.current_architecture,
                st.session_state.current_scenario,
            )
            delta = alt_result.total_monthly_usd - pricing_result.total_monthly_usd
            st.metric(
                f"Cost in {new_region}",
                f"${alt_result.total_monthly_usd:,.2f}",
                delta=f"${delta:+,.2f} vs us-east-1",
            )

        st.caption(pricing_result.disclaimer)
        st.caption(
            "Source: AWS public pricing API · " + pricing_result.pricing_date
        )


# ===================================================================
# TAB 5 — Growth Roadmap
# ===================================================================
with tab_growth:
    if st.session_state.current_scenario is None:
        st.info("Run an analysis first, then return here to see your growth trajectory.")
    else:
        st.subheader("24-month growth trajectory")
        st.caption("How your architecture evolves as your workload grows.")

        _gr_col1, _gr_col2 = st.columns(2)
        with _gr_col1:
            _gr_rate_pct = st.slider(
                "Monthly user growth rate",
                1, 20, 5, 1,
                format="%d%%",
                help="Compound monthly growth rate applied to user count",
            )
        with _gr_col2:
            _gr_months = st.slider("Months to simulate", 6, 24, 24, 6)

        if st.button("Simulate Growth", type="primary", use_container_width=True):
            with st.spinner("Simulating growth trajectory..."):
                from storage_advisor.analytics.trajectory import GrowthTrajectorySimulator
                _gr_sim = GrowthTrajectorySimulator()
                st.session_state.trajectory = _gr_sim.simulate(
                    st.session_state.current_scenario,
                    months=_gr_months,
                    user_growth_rate=_gr_rate_pct / 100.0,
                )

        if "trajectory" not in st.session_state:
            st.info("Click 'Simulate Growth' to see your architecture roadmap.")
        else:
            import pandas as pd
            traj = st.session_state.trajectory

            with st.container(border=True):
                st.markdown(traj.summary)

            _k1, _k2, _k3, _k4 = st.columns(4)
            _k1.metric("Months stable", f"{traj.architecture_stable_until}")
            _k2.metric("Tipping points", f"{len(traj.tipping_points)}")
            _k3.metric(
                "Cost at month 1",
                f"${traj.snapshots[0].real_cost_usd:,.0f}/mo",
            )
            _k4.metric(
                f"Cost at month {traj.months_simulated}",
                f"${traj.snapshots[-1].real_cost_usd:,.0f}/mo",
                delta=f"+${traj.snapshots[-1].real_cost_usd - traj.snapshots[0].real_cost_usd:,.0f}",
            )

            import plotly.graph_objects as go
            _months_list = [s.month for s in traj.snapshots]

            _fig_traj = go.Figure()
            _fig_traj.add_trace(go.Scatter(
                x=_months_list,
                y=[s.storage_gb for s in traj.snapshots],
                name="Raw storage (GB)",
                line=dict(color="#EF4444", width=2),
                yaxis="y1",
            ))
            _fig_traj.add_trace(go.Scatter(
                x=_months_list,
                y=[s.estimated_storage_gb for s in traj.snapshots],
                name="Optimized storage (GB)",
                line=dict(color="#10B981", width=2, dash="dash"),
                yaxis="y1",
            ))
            _fig_traj.add_trace(go.Scatter(
                x=_months_list,
                y=[s.real_cost_usd for s in traj.snapshots],
                name="Monthly AWS cost ($)",
                line=dict(color="#5B4FDC", width=2),
                yaxis="y2",
            ))

            for _tp in traj.tipping_points:
                _tp_color = (
                    "#EF4444" if _tp.severity == "ESCALATION"
                    else "#F59E0B" if _tp.severity == "NEW_TECHNIQUE"
                    else "#6B7280"
                )
                _fig_traj.add_vline(
                    x=_tp.month,
                    line_dash="dot",
                    line_color=_tp_color,
                    annotation_text=_tp.technique_id.replace("_", " "),
                    annotation_position="top",
                )

            _fig_traj.update_layout(
                title="Storage growth and cost trajectory",
                xaxis_title="Month",
                yaxis=dict(title="Storage (GB)", side="left"),
                yaxis2=dict(title="Monthly Cost (USD)", side="right", overlaying="y"),
                legend=dict(x=0, y=1),
                hovermode="x unified",
            )
            st.plotly_chart(_fig_traj, use_container_width=True)

            st.subheader("Architecture tipping points")
            if not traj.tipping_points:
                st.success(
                    f"Your initial architecture handles the full "
                    f"{traj.months_simulated}-month growth period without changes."
                )
            else:
                for _tp in traj.tipping_points:
                    _tp_icon = (
                        "\U0001f534" if _tp.severity == "ESCALATION"
                        else "\U0001f7e1" if _tp.severity == "NEW_TECHNIQUE"
                        else "\U0001f535"
                    )
                    with st.expander(f"{_tp_icon} Month {_tp.month} — {_tp.trigger}"):
                        st.write(f"**What changed:** {_tp.old_state} → {_tp.new_state}")
                        st.write(f"**Why:** {_tp.description}")
                        st.write(f"**Severity:** {_tp.severity}")

            st.subheader("Technique evolution over time")
            _all_techs = list({
                t for s in traj.snapshots for t in s.top_techniques
            })
            if _all_techs:
                _heatmap_data = pd.DataFrame(
                    {
                        t: [
                            1 if t in s.required_techniques
                            else 0.5 if t in s.top_techniques
                            else 0
                            for s in traj.snapshots
                        ]
                        for t in sorted(_all_techs)
                    },
                    index=[f"M{s.month}" for s in traj.snapshots],
                ).T

                _fig_heat = px.imshow(
                    _heatmap_data,
                    color_continuous_scale=[
                        [0, "white"], [0.5, "#93C5FD"], [1, "#5B4FDC"],
                    ],
                    title="Technique presence by month (dark = REQUIRED, light = RECOMMENDED)",
                    labels=dict(x="Month", y="Technique", color="Status"),
                )
                _fig_heat.update_layout(coloraxis_showscale=False)
                st.plotly_chart(_fig_heat, use_container_width=True)
                st.caption(
                    "Dark blue = REQUIRED · Light blue = RECOMMENDED · White = not needed"
                )


# ===================================================================
# TAB 6 — Why?
# ===================================================================
with tab_why:
    if st.session_state.current_result is None:
        st.info("Run analysis first (Architect tab).")
    else:
        result = st.session_state.current_result

        # AI explanation
        st.subheader("Reasoning chain")
        exp = st.session_state.current_explanation
        with st.container(border=True):
            st.markdown(exp.text)
            source_label = (
                "✨ Amazon Bedrock"
                if exp.source == "bedrock"
                else "\U0001f4cb Structured summary"
            )
            st.caption(f"Explanation source: {source_label}")

        st.divider()

        # Problem → Recommendation chain
        st.subheader("Requirement → Problem → Recommendation")
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sorted_problems = sorted(
            result.detected_problems,
            key=lambda p: severity_order.get(str(p.get("severity", "")), 99),
        )
        for problem in sorted_problems:
            pid = problem.get("problem_id", "unknown")
            sev = problem.get("severity", "MEDIUM")
            evidence = problem.get("evidence", {})

            matching_recs = [
                r for r in result.recommendations if pid in r.problems_solved
            ]

            icon = (
                "\U0001f534" if sev == "CRITICAL"
                else "\U0001f7e1" if sev == "HIGH"
                else "\U0001f535"
            )
            with st.expander(f"{icon} {pid} ({sev})"):
                st.write(f"**Evidence:** {evidence}")
                if matching_recs:
                    st.write("**Addressed by:**")
                    for r in matching_recs[:3]:
                        st.write(
                            f"  → {r.technique_id} [{r.priority}]: "
                            f"{r.rationale}"
                        )
                else:
                    st.write(
                        "No specific technique directly addresses this pressure."
                    )


# ===================================================================
# TAB 5 — Analytics
# ===================================================================
with tab_analytics:
    st.caption(
        "Patterns from 2,000 synthetic scenarios — "
        "model-based data, not production telemetry."
    )

    if components["store"] is None:
        st.warning(
            "Analytics data not available. "
            "Run the scenario generator first to create the Parquet file."
        )
    else:
        charts = _load_charts(components["store"])

        # Row 1: KPI cards
        st.plotly_chart(charts["kpi_cards"], use_container_width=True)

        # Row 2
        ac1, ac2 = st.columns(2)
        ac1.plotly_chart(
            charts["technique_frequency"], use_container_width=True,
        )
        ac2.plotly_chart(
            charts["domain_comparison"], use_container_width=True,
        )

        # Row 3: savings scatter
        st.plotly_chart(charts["savings_scatter"], use_container_width=True)

        # Row 4
        ac3, ac4 = st.columns(2)
        ac3.plotly_chart(
            charts["cooccurrence_heatmap"], use_container_width=True,
        )
        ac4.plotly_chart(
            charts["cooccurrence_network"], use_container_width=True,
        )

        # Row 5: ML comparison
        st.divider()
        try:
            ml = _load_ml()
            st.subheader("Rule engine vs ML experiment")
            st.caption(
                "⚠️ ML EXPERIMENT — trained on synthetic data only"
            )

            mc1, mc2 = st.columns(2)
            mc1.metric("RandomForest macro F1", f"{ml.macro_f1:.3f}")
            mc2.metric(
                "Top-5 rule agreement",
                f"{ml.rule_agreement_rate * 100:.1f}%",
            )

            st.write(
                "**Insight:** The RandomForest learns per-technique presence "
                "near-perfectly (F1=0.997) but its probability ranking differs "
                "from the rule engine’s priority ordering in ~60% of cases "
                "— demonstrating why deterministic reasoning matters for "
                "production architecture decisions."
            )

            st.dataframe(
                ml.per_technique_metrics.sort_values("f1", ascending=False),
            )

            st.plotly_chart(
                px.bar(
                    ml.feature_importances.head(10),
                    x="importance",
                    y="feature",
                    orientation="h",
                    title="Top 10 features driving ML recommendations",
                ),
                use_container_width=True,
            )
        except Exception:
            st.info("ML experiment not available.")


# ===================================================================
# TAB 6 — What-if
# ===================================================================
with tab_whatif:
    if st.session_state.current_scenario is None:
        st.info(
            "Run an analysis first (Architect tab), then return here "
            "to modify assumptions."
        )
    else:
        scenario = st.session_state.current_scenario

        st.subheader("Modify assumptions and recalculate")

        wc1, wc2 = st.columns(2)

        with wc1:
            new_growth = st.slider(
                "Daily growth (GB/day)", 0, 10_000,
                value=int(scenario.daily_growth_gb), step=50,
                key="wi_growth",
            )
            new_latency = st.slider(
                "Latency target (ms)", 1, 5_000,
                value=int(scenario.latency_requirement_ms), step=10,
                key="wi_latency",
            )
            new_users = st.slider(
                "Users", 1_000, 50_000_000,
                value=int(scenario.expected_users), step=100_000,
                key="wi_users",
            )
            new_retention = st.slider(
                "Retention (years)", 0, 20,
                value=int(scenario.retention_years),
                key="wi_retention",
            )

        with wc2:
            st.markdown("**Parameter comparison**")
            st.table({
                "Parameter": [
                    "Daily growth", "Latency", "Users", "Retention",
                ],
                "Baseline": [
                    f"{scenario.daily_growth_gb:.0f} GB/day",
                    f"{scenario.latency_requirement_ms:.0f} ms",
                    f"{scenario.expected_users:,}",
                    f"{scenario.retention_years:.0f} years",
                ],
                "Modified": [
                    f"{new_growth} GB/day",
                    f"{new_latency} ms",
                    f"{new_users:,}",
                    f"{new_retention} years",
                ],
            })

        if st.button("Recalculate", type="primary", key="wi_recalc"):
            with st.spinner("Recalculating…"):
                new_concurrent = max(1, min(new_users // 10, new_users))
                modified = scenario.model_copy(update={
                    "daily_growth_gb": float(new_growth),
                    "latency_requirement_ms": float(new_latency),
                    "expected_users": new_users,
                    "concurrent_users": new_concurrent,
                    "retention_years": float(new_retention),
                })
                wf_result = components["whatif"].compare(scenario, modified)
                st.session_state["whatif_result"] = wf_result

        if "whatif_result" in st.session_state:
            wf = st.session_state["whatif_result"]
            st.markdown(f"**Summary:** {wf.summary}")

            wm1, wm2, wm3 = st.columns(3)
            wm1.metric(
                "Storage reduction",
                f"{wf.modified_impact.storage.estimated_reduction_pct:.1f}%",
                delta=f"{wf.storage_delta_pct:+.1f}pp",
            )
            wm2.metric(
                "Cost reduction",
                f"{wf.modified_impact.cost.estimated_savings_pct:.1f}%",
                delta=f"{wf.cost_delta_pct:+.1f}pp",
            )
            wm3.metric(
                "Latency improvement",
                f"{wf.modified_impact.latency.estimated_improvement_pct:.1f}%",
                delta=f"{wf.latency_delta_pct:+.1f}pp",
            )

            if wf.added_techniques:
                st.success(
                    f"Added to strategy: {', '.join(wf.added_techniques)}"
                )
            if wf.removed_techniques:
                st.warning(
                    f"Removed from strategy: {', '.join(wf.removed_techniques)}"
                )
            if wf.changed_priorities:
                for change in wf.changed_priorities:
                    st.info(
                        f"{change['technique_id']}: "
                        f"{change['old_priority']} → {change['new_priority']}"
                    )
