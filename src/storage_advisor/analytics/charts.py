"""Chart generators — Plotly figures built from the AnalyticsStore."""

from __future__ import annotations

import numpy as np
import networkx as nx
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from storage_advisor.analytics.store import AnalyticsStore

PRIMARY = "#5B4FDC"
SECONDARY = "#1DB9A0"
ACCENT = "#F59E0B"

_LAYOUT_DEFAULTS = dict(
    font=dict(family="Inter, system-ui, sans-serif", size=13),
    plot_bgcolor="#FAFAFA",
    paper_bgcolor="white",
    margin=dict(t=80, b=60, l=60, r=40),
)


def _readable(name: str) -> str:
    return name.replace("_", " ")


# --------------------------------------------------------------------------
# 1. KPI indicator cards
# --------------------------------------------------------------------------

def kpi_cards(store: AnalyticsStore) -> go.Figure:
    kpi = store.kpi_summary()
    fig = make_subplots(
        rows=1, cols=4,
        specs=[[{"type": "indicator"}] * 4],
    )
    items = [
        ("Total scenarios", kpi["total_scenarios"], ""),
        ("Avg storage reduction", kpi["avg_storage_reduction_pct"], "%"),
        ("Avg cost reduction", kpi["avg_cost_reduction_pct"], "%"),
        ("Avg latency improvement", kpi["avg_latency_improvement_pct"], "%"),
    ]
    for i, (title, value, suffix) in enumerate(items, 1):
        fig.add_trace(
            go.Indicator(
                mode="number+delta",
                value=value,
                delta=dict(reference=0, valueformat=".1f"),
                number=dict(suffix=suffix, valueformat=".1f" if suffix else ","),
                title=dict(text=title, font=dict(size=14)),
                domain=dict(row=0, column=i - 1),
            ),
            row=1, col=i,
        )
    fig.update_layout(
        title="Synthetic dataset KPIs — model-based estimates",
        **_LAYOUT_DEFAULTS,
        height=250,
    )
    return fig


# --------------------------------------------------------------------------
# 2. Technique frequency horizontal bar
# --------------------------------------------------------------------------

def technique_frequency_chart(store: AnalyticsStore) -> go.Figure:
    df = store.technique_frequency()
    df = df.sort_values("pct_of_scenarios", ascending=True)
    df["label"] = df["technique_id"].apply(_readable)

    fig = go.Figure(go.Bar(
        x=df["pct_of_scenarios"],
        y=df["label"],
        orientation="h",
        marker_color=PRIMARY,
        text=df["pct_of_scenarios"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside",
    ))
    fig.update_layout(
        title=dict(
            text=(
                "Technique recommendation frequency across 2,000 scenarios"
                "<br><sup>Synthetic data — not empirical production measurements</sup>"
            ),
        ),
        xaxis_title="% of scenarios",
        yaxis_title="",
        **_LAYOUT_DEFAULTS,
        height=600,
        xaxis=dict(range=[0, 110]),
    )
    return fig


# --------------------------------------------------------------------------
# 3. Domain comparison grouped bar
# --------------------------------------------------------------------------

def domain_comparison_chart(store: AnalyticsStore) -> go.Figure:
    df = store.domain_summary()
    fig = go.Figure([
        go.Bar(
            name="Avg storage reduction %",
            x=df["domain"],
            y=df["avg_storage_reduction"],
            marker_color=PRIMARY,
        ),
        go.Bar(
            name="Avg cost reduction %",
            x=df["domain"],
            y=df["avg_cost_reduction"],
            marker_color=SECONDARY,
        ),
    ])
    fig.update_layout(
        title="Average impact by business domain",
        barmode="group",
        yaxis_title="%",
        **_LAYOUT_DEFAULTS,
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


# --------------------------------------------------------------------------
# 4. Savings scatter (bubble)
# --------------------------------------------------------------------------

def savings_scatter(store: AnalyticsStore) -> go.Figure:
    df = store.savings_by_technique()
    max_count = df["scenario_count"].max()
    df["size"] = df["scenario_count"] / max_count * 40

    fig = px.scatter(
        df,
        x="avg_storage_reduction",
        y="avg_cost_reduction",
        size="size",
        color="avg_latency_improvement",
        color_continuous_scale="Viridis",
        hover_name="technique_id",
        hover_data={
            "avg_storage_reduction": ":.2f",
            "avg_cost_reduction": ":.2f",
            "avg_latency_improvement": ":.2f",
            "scenario_count": True,
            "size": False,
        },
    )
    fig.update_layout(
        title=(
            "Storage vs cost reduction by technique"
            "<br><sup>bubble = scenario count, color = latency improvement</sup>"
        ),
        xaxis_title="Avg storage reduction %",
        yaxis_title="Avg cost reduction %",
        coloraxis_colorbar_title="Latency<br>improvement %",
        **_LAYOUT_DEFAULTS,
        height=550,
    )
    return fig


# --------------------------------------------------------------------------
# 5. Co-occurrence heatmap
# --------------------------------------------------------------------------

def cooccurrence_heatmap(store: AnalyticsStore) -> go.Figure:
    df = store.technique_cooccurrence()
    techniques = sorted(
        set(df["technique_a"].tolist() + df["technique_b"].tolist())
    )
    n = len(techniques)
    idx = {t: i for i, t in enumerate(techniques)}
    matrix = np.zeros((n, n), dtype=int)
    for _, row in df.iterrows():
        i, j = idx[row["technique_a"]], idx[row["technique_b"]]
        matrix[i][j] = int(row["cooccurrence_count"])
        matrix[j][i] = int(row["cooccurrence_count"])

    labels = [_readable(t) for t in techniques]
    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=labels,
        y=labels,
        colorscale="Blues",
        hovertemplate="%{y} × %{x}: %{z}<extra></extra>",
    ))
    fig.update_layout(
        title=(
            "Technique co-occurrence matrix"
            "<br><sup>Diagonal is 0 — a technique does not co-occur with itself</sup>"
        ),
        **_LAYOUT_DEFAULTS,
        height=700,
        width=900,
        xaxis=dict(tickangle=45),
        yaxis=dict(autorange="reversed"),
    )
    return fig


# --------------------------------------------------------------------------
# 6. Co-occurrence network
# --------------------------------------------------------------------------

def cooccurrence_network(
    store: AnalyticsStore, min_cooccurrence: int = 50,
) -> go.Figure:
    cooc = store.technique_cooccurrence()
    freq = store.technique_frequency()
    freq_map = dict(zip(freq["technique_id"], freq["recommendation_count"]))

    G = nx.Graph()
    for t in freq["technique_id"]:
        G.add_node(t)

    edges = cooc[cooc["cooccurrence_count"] >= min_cooccurrence]
    max_weight = edges["cooccurrence_count"].max() if len(edges) else 1
    for _, row in edges.iterrows():
        G.add_edge(
            row["technique_a"], row["technique_b"],
            weight=int(row["cooccurrence_count"]),
        )

    pos = nx.spring_layout(G, seed=42, k=1.5)

    edge_traces = []
    for u, v, d in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        opacity = 0.15 + 0.75 * (d["weight"] / max_weight)
        edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(width=1, color=f"rgba(150,150,150,{opacity:.2f})"),
            hoverinfo="skip",
            showlegend=False,
        ))

    max_freq = max(freq_map.values()) if freq_map else 1
    node_x, node_y, node_size, node_text = [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        count = freq_map.get(node, 0)
        node_size.append(10 + 30 * (count / max_freq))
        node_text.append(f"{_readable(node)}<br>{count} scenarios")

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode="markers+text",
        marker=dict(size=node_size, color=PRIMARY, line=dict(width=1, color="white")),
        text=[_readable(n) for n in G.nodes()],
        textposition="top center",
        textfont=dict(size=9),
        hovertext=node_text,
        hoverinfo="text",
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title=f"Technique co-occurrence network (edges >= {min_cooccurrence} scenarios)",
        **_LAYOUT_DEFAULTS,
        height=650,
        width=900,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig


# --------------------------------------------------------------------------
# All charts
# --------------------------------------------------------------------------

def all_charts(store: AnalyticsStore) -> dict[str, go.Figure]:
    return {
        "kpi_cards": kpi_cards(store),
        "technique_frequency": technique_frequency_chart(store),
        "domain_comparison": domain_comparison_chart(store),
        "savings_scatter": savings_scatter(store),
        "cooccurrence_heatmap": cooccurrence_heatmap(store),
        "cooccurrence_network": cooccurrence_network(store),
    }
