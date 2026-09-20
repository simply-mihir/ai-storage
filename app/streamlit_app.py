"""Streamlit UI for AI Data Architect — storage architecture advisor."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

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


def load_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * { font-family: 'Inter', sans-serif !important; }

    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #1A1A2E;
        padding: 8px;
        border-radius: 12px;
        border: 1px solid #2D2D4E;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        color: #94A3B8;
        font-weight: 500;
        font-size: 0.85rem;
        padding: 8px 16px;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        background: #5B4FDC !important;
        color: white !important;
    }

    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
        border: 1px solid #2D2D4E;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 24px rgba(91,79,220,0.1);
    }
    [data-testid="metric-container"]:hover {
        border-color: #5B4FDC;
        box-shadow: 0 4px 24px rgba(91,79,220,0.3);
        transform: translateY(-2px);
        transition: all 0.2s ease;
    }

    .stButton > button {
        background: linear-gradient(135deg, #5B4FDC 0%, #7C3AED 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(91,79,220,0.4);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(91,79,220,0.6);
    }

    .streamlit-expanderHeader {
        background: #1A1A2E;
        border: 1px solid #2D2D4E;
        border-radius: 8px;
        font-weight: 500;
    }
    .streamlit-expanderContent {
        background: #16213E;
        border: 1px solid #2D2D4E;
        border-top: none;
        border-radius: 0 0 8px 8px;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #1A1A2E;
        border: 1px solid #2D2D4E !important;
        border-radius: 12px;
    }

    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background: #1A1A2E;
        border: 1px solid #2D2D4E;
        border-radius: 8px;
        color: #E2E8F0;
    }
    .stSelectbox select, .stMultiSelect {
        background: #1A1A2E;
        border: 1px solid #2D2D4E;
    }

    [data-testid="stSidebar"] {
        background: #0F0F1A;
        border-right: 1px solid #2D2D4E;
    }

    .stDataFrame {
        border: 1px solid #2D2D4E;
        border-radius: 8px;
    }

    .stSuccess { background: rgba(16,185,129,0.1); border-color: #10B981; }
    .stWarning { background: rgba(245,158,11,0.1); border-color: #F59E0B; }
    .stInfo    { background: rgba(91,79,220,0.1);  border-color: #5B4FDC; }

    hr { border-color: #2D2D4E; }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0F0F1A; }
    ::-webkit-scrollbar-thumb {
        background: #5B4FDC;
        border-radius: 3px;
    }

    .ada-header {
        background: linear-gradient(135deg, #5B4FDC 0%, #7C3AED 50%, #1DB9A0 100%);
        background-size: 200% 200%;
        animation: gradientShift 6s ease infinite;
        border-radius: 16px;
        padding: 32px;
        margin-bottom: 24px;
        text-align: center;
    }
    @keyframes gradientShift {
        0%   { background-position: 0% 50%; }
        50%  { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .ada-header h1 {
        color: white !important;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .ada-header p {
        color: rgba(255,255,255,0.8) !important;
        margin: 8px 0 0 0;
        font-size: 1rem;
    }

    .badge-required {
        background: rgba(239,68,68,0.2);
        color: #F87171;
        border: 1px solid rgba(239,68,68,0.4);
        border-radius: 6px;
        padding: 2px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .badge-recommended {
        background: rgba(245,158,11,0.2);
        color: #FCD34D;
        border: 1px solid rgba(245,158,11,0.4);
        border-radius: 6px;
        padding: 2px 10px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-optional {
        background: rgba(100,116,139,0.2);
        color: #94A3B8;
        border: 1px solid rgba(100,116,139,0.4);
        border-radius: 6px;
        padding: 2px 10px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .tp-card-escalation {
        background: rgba(239,68,68,0.08);
        border-left: 4px solid #EF4444;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin: 8px 0;
    }
    .tp-card-new {
        background: rgba(245,158,11,0.08);
        border-left: 4px solid #F59E0B;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin: 8px 0;
    }
    .tp-card-arch {
        background: rgba(91,79,220,0.08);
        border-left: 4px solid #5B4FDC;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin: 8px 0;
    }

    .stat-card {
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
        border: 1px solid #2D2D4E;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        transition: all 0.2s ease;
    }
    .stat-card:hover {
        border-color: #5B4FDC;
        transform: translateY(-2px);
    }
    .stat-card .value {
        font-size: 2rem;
        font-weight: 700;
        color: #5B4FDC;
        line-height: 1;
    }
    .stat-card .label {
        font-size: 0.8rem;
        color: #64748B;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stat-card .delta {
        font-size: 0.85rem;
        color: #10B981;
        margin-top: 4px;
        font-weight: 500;
    }

    .arch-card {
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
        border: 1px solid #2D2D4E;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        transition: all 0.2s ease;
    }
    .arch-card:hover {
        border-color: #5B4FDC;
        box-shadow: 0 4px 20px rgba(91,79,220,0.2);
        transform: translateY(-1px);
    }
    .arch-card .service-name {
        font-size: 1rem;
        font-weight: 600;
        color: #E2E8F0;
    }
    .arch-card .domain-tag {
        font-size: 0.75rem;
        color: #1DB9A0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    </style>
    """, unsafe_allow_html=True)


load_css()

st.markdown("""
<div class="ada-header">
  <h1>AI Data Architect</h1>
  <p>Workload-aware storage strategy &middot; Real AWS pricing &middot;
     Explainable reasoning &middot; Terraform-ready</p>
</div>
""", unsafe_allow_html=True)

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

st.sidebar.markdown("""
<div style="text-align:center; padding:16px 0 8px 0;">
  <div style="font-size:2rem">&#9889;</div>
  <div style="font-weight:700; font-size:1.1rem;
              color:#E2E8F0;">AI Data Architect</div>
  <div style="font-size:0.75rem; color:#475569;
              margin-top:4px;">3-Day AWS Hackathon MVP</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()

st.sidebar.markdown("**Engine**")
_kb_count = len(components["techniques"])
st.sidebar.markdown(f"""
<div style="font-size:0.8rem; color:#94A3B8; line-height:1.8;">
  &#128451; {_kb_count} techniques loaded<br>
  &#9989; 222 tests passing<br>
  &#128202; 2,000 synthetic scenarios<br>
  &#128290; Rule engine v1.0
</div>
""", unsafe_allow_html=True)

st.sidebar.divider()

bedrock = components["bedrock"]
st.sidebar.markdown("**AI Provider**")
if bedrock.available:
    st.sidebar.success("Amazon Bedrock (primary)")
elif bedrock.groq_available:
    st.sidebar.warning("Groq fallback active")
else:
    st.sidebar.info("Structured engine (offline)")

st.sidebar.divider()

st.sidebar.markdown("**AWS**")
_s3_ok = False
try:
    from storage_advisor.integrations.aws import S3Store
    _s3_ok = True
except Exception:
    pass
st.sidebar.markdown(f"""
<div style="font-size:0.8rem; color:#94A3B8; line-height:1.8;">
  S3: {"&#9989; Connected" if _s3_ok else "&#128203; Local mode"}<br>
  DB: SQLite (local)<br>
  Pricing: &#9989; Live AWS API
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
for _k in [
    "current_scenario", "current_result", "current_impact",
    "current_architecture", "current_explanation",
]:
    if _k not in st.session_state:
        st.session_state[_k] = None

def _render_architecture_diagram(architecture):
    _domain_positions = {
        "cache": (150, 120),
        "transactional": (400, 120),
        "object": (650, 120),
        "analytics": (400, 280),
        "archive": (650, 280),
    }
    _domain_colors = {
        "cache": "#F59E0B",
        "transactional": "#5B4FDC",
        "object": "#1DB9A0",
        "analytics": "#EC4899",
        "archive": "#64748B",
    }
    _seen = set()
    _nodes = []
    _labels = []
    for comp in architecture.components:
        if comp.workload_domain in _seen:
            continue
        _seen.add(comp.workload_domain)
        pos = _domain_positions.get(comp.workload_domain, (400, 200))
        color = _domain_colors.get(comp.workload_domain, "#5B4FDC")
        short = comp.service.replace("Amazon ", "").replace(" for PostgreSQL", "")
        _nodes.append(
            f'<rect x="{pos[0]-70}" y="{pos[1]-25}" width="140" height="50" '
            f'rx="10" fill="{color}22" stroke="{color}" stroke-width="2"/>'
        )
        _labels.append(
            f'<text x="{pos[0]}" y="{pos[1]-5}" text-anchor="middle" '
            f'fill="{color}" font-size="11" font-weight="600">{short[:18]}</text>'
            f'<text x="{pos[0]}" y="{pos[1]+12}" text-anchor="middle" '
            f'fill="#94A3B8" font-size="9">{comp.workload_domain.upper()}</text>'
        )

    _arrows = ""
    _arrow_seen = set()
    for comp in architecture.components:
        if comp.workload_domain in ("cache", "transactional", "object"):
            if comp.workload_domain not in _arrow_seen:
                _arrow_seen.add(comp.workload_domain)
                pos = _domain_positions.get(comp.workload_domain, (400, 120))
                _arrows += (
                    f'<line x1="400" y1="60" x2="{pos[0]}" y2="{pos[1]-25}" '
                    f'stroke="#2D2D4E" stroke-width="1.5" stroke-dasharray="4,3" '
                    f'marker-end="url(#arrow)"/>'
                )

    _summary_text = architecture.summary[:60] if hasattr(architecture, "summary") else ""
    svg = f"""
    <svg viewBox="0 0 820 360" xmlns="http://www.w3.org/2000/svg"
         style="background:#0F0F1A; border-radius:12px;
                border:1px solid #2D2D4E; width:100%">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8"
                refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="#2D2D4E"/>
        </marker>
      </defs>
      <text x="16" y="24" fill="#475569" font-size="10"
            font-family="monospace">ARCHITECTURE &middot; {_summary_text}</text>
      <rect x="335" y="20" width="130" height="40" rx="8"
            fill="#5B4FDC22" stroke="#5B4FDC" stroke-width="2"/>
      <text x="400" y="38" text-anchor="middle" fill="#A78BFA"
            font-size="11" font-weight="600">Application / Users</text>
      <text x="400" y="53" text-anchor="middle" fill="#64748B"
            font-size="9">Entry point</text>
      {_arrows}
      {"".join(_nodes)}
      {"".join(_labels)}
    </svg>
    """
    st.markdown(svg, unsafe_allow_html=True)


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
            _render_architecture_diagram(arch)
            st.markdown("")

            _domain_icons = {
                "transactional": "&#128451;",
                "object": "&#128230;",
                "cache": "&#9889;",
                "analytics": "&#128202;",
                "archive": "&#128451;",
            }
            _priority_badge = {
                "REQUIRED": '<span class="badge-required">REQUIRED</span>',
                "RECOMMENDED": '<span class="badge-recommended">RECOMMENDED</span>',
                "OPTIONAL": '<span class="badge-optional">OPTIONAL</span>',
            }

            from itertools import groupby
            _sorted_components = sorted(arch.components, key=lambda c: c.workload_domain)
            for _domain, _group in groupby(_sorted_components, key=lambda c: c.workload_domain):
                _icon = _domain_icons.get(_domain, "&#128295;")
                st.markdown(f"**{_icon} {_domain.upper()} TIER**")
                for comp in _group:
                    _badge = _priority_badge.get(comp.priority, "")
                    _notes = "<br>".join(f"&bull; {n}" for n in comp.configuration_notes[:3])
                    _by = ", ".join(comp.required_by)
                    st.markdown(f"""
                    <div class="arch-card">
                      <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="service-name">{comp.service}</span>
                        {_badge}
                      </div>
                      <div class="domain-tag" style="margin-top:4px;">{comp.workload_domain}</div>
                      <div style="font-size:0.8rem; color:#64748B; margin-top:8px;">
                        {_notes}
                      </div>
                      <div style="font-size:0.75rem; color:#475569; margin-top:6px;">
                        Required by: {_by}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

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
        with c1:
            st.markdown(f"""
            <div class="stat-card">
              <div class="value">{impact.storage.projected_storage_gb:,.0f} GB</div>
              <div class="label">Optimized Storage</div>
              <div class="delta">&darr; {impact.storage.estimated_reduction_pct:.1f}% reduction</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="stat-card">
              <div class="value">${impact.cost.estimated_monthly_optimized_usd:,.0f}</div>
              <div class="label">Monthly Cost</div>
              <div class="delta">&darr; {impact.cost.estimated_savings_pct:.1f}% savings</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="stat-card">
              <div class="value">{impact.latency.estimated_optimized_latency_ms:.0f}ms</div>
              <div class="label">Latency</div>
              <div class="delta">&darr; {impact.latency.estimated_improvement_pct:.1f}% faster</div>
            </div>
            """, unsafe_allow_html=True)

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
                paper_bgcolor="#0F0F1A", plot_bgcolor="#1A1A2E",
                font=dict(color="#E2E8F0"),
                xaxis=dict(gridcolor="#2D2D4E"), yaxis=dict(gridcolor="#2D2D4E"),
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
                paper_bgcolor="#0F0F1A", plot_bgcolor="#1A1A2E",
                font=dict(color="#E2E8F0"),
                xaxis=dict(gridcolor="#2D2D4E"), yaxis=dict(gridcolor="#2D2D4E"),
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
            xaxis=dict(range=[0, 100], gridcolor="#2D2D4E"),
            yaxis=dict(gridcolor="#2D2D4E"),
            height=250,
            margin=dict(l=20, r=20, t=40, b=20),
            barmode="overlay",
            paper_bgcolor="#0F0F1A", plot_bgcolor="#1A1A2E",
            font=dict(color="#E2E8F0"),
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
            color_continuous_scale=[[0, "#1A1A2E"], [0.5, "#3B3B8E"], [1, "#5B4FDC"]],
        )
        fig_cost.update_layout(
            paper_bgcolor="#0F0F1A", plot_bgcolor="#1A1A2E",
            font=dict(color="#E2E8F0"),
            xaxis=dict(gridcolor="#2D2D4E"), yaxis=dict(gridcolor="#2D2D4E"),
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
                yaxis=dict(title="Storage (GB)", side="left", gridcolor="#2D2D4E"),
                yaxis2=dict(title="Monthly Cost (USD)", side="right", overlaying="y", gridcolor="#2D2D4E"),
                legend=dict(x=0, y=1, bgcolor="#1A1A2E", bordercolor="#2D2D4E"),
                hovermode="x unified",
                paper_bgcolor="#0F0F1A", plot_bgcolor="#1A1A2E",
                font=dict(color="#E2E8F0"),
                xaxis=dict(gridcolor="#2D2D4E"),
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
                    _tp_class = {
                        "ESCALATION": "tp-card-escalation",
                        "NEW_TECHNIQUE": "tp-card-new",
                        "ARCHITECTURE_CHANGE": "tp-card-arch",
                    }.get(_tp.severity, "tp-card-new")
                    _tp_icon = {
                        "ESCALATION": "&#128308;",
                        "NEW_TECHNIQUE": "&#128993;",
                        "ARCHITECTURE_CHANGE": "&#128309;",
                    }.get(_tp.severity, "&#9898;")
                    st.markdown(f"""
                    <div class="{_tp_class}">
                      <div style="font-weight:600; color:#E2E8F0; margin-bottom:4px;">
                        {_tp_icon} Month {_tp.month} &mdash; {_tp.trigger}
                      </div>
                      <div style="font-size:0.85rem; color:#94A3B8;">
                        {_tp.description}
                      </div>
                      <div style="font-size:0.75rem; color:#475569; margin-top:6px;">
                        {_tp.old_state} &rarr; {_tp.new_state} &middot; {_tp.severity}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

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
                        [0, "#1A1A2E"], [0.5, "#3B3B8E"], [1, "#5B4FDC"],
                    ],
                    title="Technique presence by month (dark = REQUIRED, light = RECOMMENDED)",
                    labels=dict(x="Month", y="Technique", color="Status"),
                )
                _fig_heat.update_layout(
                    coloraxis_showscale=False,
                    paper_bgcolor="#0F0F1A", plot_bgcolor="#1A1A2E",
                    font=dict(color="#E2E8F0"),
                )
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
            source_labels = {
                "bedrock": "✨ Amazon Bedrock",
                "groq": "✨ Groq · Qwen 3.8 27B",
                "structured_fallback": "\U0001f4cb Structured summary",
            }
            source_label = source_labels.get(exp.source, exp.source)
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

        st.divider()
        st.subheader("\U0001f4c4 Architecture Decision Document")

        if st.button("Generate Architecture Story",
                     type="primary", use_container_width=True):
            with st.spinner("Generating architecture decision document..."):
                from storage_advisor.export.story import ArchitectureStoryGenerator
                gen = ArchitectureStoryGenerator()

                traj = st.session_state.get("trajectory", None)
                banded = st.session_state.get("banded_impact", None)

                story = gen.generate(
                    st.session_state.current_scenario,
                    st.session_state.current_result,
                    st.session_state.current_impact,
                    st.session_state.current_architecture,
                    trajectory=traj,
                    banded_impact=banded,
                )
                st.session_state.architecture_story = story

        if "architecture_story" in st.session_state:
            story = st.session_state.architecture_story
            with st.container(border=True):
                st.markdown(story.full_document)
                st.caption(
                    f"Generated by AI Data Architect rule engine · "
                    f"{story.word_count} words · {story.generated_at[:10]}"
                )

            st.download_button(
                label="⬇️ Download as Markdown",
                data=story.full_document,
                file_name="architecture-decision.md",
                mime="text/markdown",
                use_container_width=True,
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
