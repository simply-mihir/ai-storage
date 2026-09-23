"""Insights module — generates Plotly figure specs from the analytics store."""

from __future__ import annotations

import plotly.graph_objects as go

from storage_advisor.analytics.eda import (
    correlation_matrix,
    industry_category_heatdata,
    technique_frequency,
)
from storage_advisor.kb.loader import discover_families, project_graph


def _theme_layout(dark: bool = True) -> dict:
    if dark:
        return {
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#F5F5F5", "size": 12},
            "coloraxis_colorbar": {"tickfont": {"color": "#A0A0A0"}},
            "margin": {"l": 60, "r": 30, "t": 50, "b": 60},
        }
    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#16181D", "size": 12},
        "coloraxis_colorbar": {"tickfont": {"color": "#5C6470"}},
        "margin": {"l": 60, "r": 30, "t": 50, "b": 60},
    }


def treemap_technique_frequency(
    parquet_path: str = "data/synthetic/scenarios.parquet",
    dark: bool = True,
) -> str:
    """Treemap of technique recommendation frequency."""
    data = technique_frequency(parquet_path)
    labels = [d["technique_id"] for d in data]
    values = [d["count"] for d in data]
    pcts = [d["pct"] for d in data]

    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=[""] * len(labels),
        values=values,
        textinfo="label+percent root",
        customdata=pcts,
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{customdata:.1f}% of scenarios<extra></extra>",
        marker={"colorscale": "Oranges" if dark else "YlOrRd"},
    ))
    fig.update_layout(
        title="Technique Frequency",
        **_theme_layout(dark),
    )
    return fig.to_json()


def heatmap_industry_savings(
    parquet_path: str = "data/synthetic/scenarios.parquet",
    dark: bool = True,
) -> str:
    """Heatmap of industry x avg storage savings."""
    heat = industry_category_heatdata(parquet_path)
    fig = go.Figure(go.Heatmap(
        z=heat["data"],
        x=heat["techniques"],
        y=heat["domains"],
        colorscale="Inferno" if dark else "YlOrRd",
        hovertemplate="Domain: %{y}<br>Technique: %{x}<br>Avg savings: %{z:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title="Industry × Avg Storage Savings (%)",
        xaxis={"tickangle": -45},
        **_theme_layout(dark),
    )
    return fig.to_json()


def heatmap_correlation(
    parquet_path: str = "data/synthetic/scenarios.parquet",
    dark: bool = True,
) -> str:
    """Correlation matrix heatmap."""
    corr = correlation_matrix(parquet_path)
    fig = go.Figure(go.Heatmap(
        z=corr["data"],
        x=corr["columns"],
        y=corr["columns"],
        colorscale="RdBu_r",
        zmid=0,
        hovertemplate="%{y} × %{x}: %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(
        title="Feature Correlation Matrix",
        xaxis={"tickangle": -45},
        **_theme_layout(dark),
    )
    return fig.to_json()


def bubble_growth_savings(
    parquet_path: str = "data/synthetic/scenarios.parquet",
    dark: bool = True,
) -> str:
    """Bubble chart: x=daily growth, y=savings%, size=users, color=domain."""
    import duckdb

    conn = duckdb.connect()
    conn.execute(
        f"CREATE VIEW scenarios AS SELECT * FROM read_parquet('{parquet_path}')"
    )
    df = conn.execute("""
        SELECT domain, daily_growth_gb, storage_reduction_pct, users
        FROM scenarios
    """).df()

    domains = df["domain"].unique()
    fig = go.Figure()
    for domain in sorted(domains):
        sub = df[df["domain"] == domain]
        fig.add_trace(go.Scatter(
            x=sub["daily_growth_gb"],
            y=sub["storage_reduction_pct"],
            mode="markers",
            name=domain,
            marker={
                "size": (sub["users"] / sub["users"].max() * 30 + 5).tolist(),
                "opacity": 0.7,
            },
            hovertemplate=(
                f"<b>{domain}</b><br>"
                "Growth: %{x:.0f} GB/day<br>"
                "Savings: %{y:.1f}%<br>"
                "<extra></extra>"
            ),
        ))
    fig.update_layout(
        title="Growth vs Savings (bubble size = users)",
        xaxis_title="Daily Growth (GB)",
        yaxis_title="Storage Savings (%)",
        **_theme_layout(dark),
    )
    return fig.to_json()


def technique_graph_spec(dark: bool = True) -> str:
    """Network graph of technique families from project_graph()."""
    import networkx as nx

    families = discover_families()
    g = project_graph()

    family_ids = {f.id for f in families}
    family_map = {f.id: f for f in families}

    category_colors = {
        "analytics": "#F97316",
        "architecture": "#14B8A6",
        "caching": "#FBBF24",
        "database": "#3B82F6",
        "infrastructure": "#8B5CF6",
        "networking": "#EC4899",
        "reliability": "#10B981",
        "security": "#EF4444",
        "storage": "#6366F1",
    }

    def to_family(node_id: str) -> str | None:
        if node_id in family_ids:
            return node_id
        prefix = node_id.split(".")[0]
        if prefix in family_ids:
            return prefix
        return None

    family_graph = nx.Graph()
    for fam in families:
        family_graph.add_node(fam.id)

    seen_edges: set[tuple[str, str, str]] = set()
    for u, v, data in g.edges(data=True):
        rel = data.get("relation", "")
        if rel == "SOLVES":
            continue
        fu, fv = to_family(u), to_family(v)
        if fu and fv and fu != fv:
            canonical = (min(fu, fv), max(fu, fv), rel)
            if canonical not in seen_edges:
                seen_edges.add(canonical)
                family_graph.add_edge(fu, fv, relation=rel)

    pos = nx.spring_layout(family_graph, seed=42, k=1.8)

    node_x, node_y, node_text, node_color, node_hover, node_custom = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for node in family_graph.nodes:
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
        node_custom.append(node)
        fam = family_map.get(node)
        cat = fam.category if fam else "unknown"
        node_color.append(category_colors.get(cat, "#999"))
        summary = fam.summary if fam else ""
        variants = len(fam.variants) if fam else 0
        node_hover.append(
            f"<b>{fam.name if fam else node}</b><br>Category: {cat}<br>Variants: {variants}<br>{summary[:90]}"
        )

    edge_traces = []
    edge_colors = {
        "SYNERGIZES": "rgba(20,184,166,0.6)" if dark else "rgba(13,148,136,0.8)",
        "CONFLICTS": "rgba(239,68,68,0.6)" if dark else "rgba(217,48,37,0.8)",
        "REQUIRES": "rgba(160,160,160,0.5)" if dark else "rgba(92,100,112,0.7)",
    }
    edge_dashes = {
        "SYNERGIZES": "solid",
        "CONFLICTS": "solid",
        "REQUIRES": "dash",
    }

    for u, v, data in family_graph.edges(data=True):
        rel = data.get("relation", "")
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_traces.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode="lines",
                line={
                    "color": edge_colors.get(rel, "gray"),
                    "width": 2,
                    "dash": edge_dashes.get(rel, "solid"),
                },
                hoverinfo="text",
                text=f"{u} — {rel} — {v}",
                showlegend=False,
            )
        )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        textfont={"size": 9, "color": "#F5F5F5" if dark else "#16181D"},
        marker={
            "size": 15,
            "color": node_color,
            "line": {"width": 1.5, "color": "#333" if dark else "#ffffff"},
        },
        customdata=node_custom,
        hoverinfo="text",
        hovertext=node_hover,
    )

    fig = go.Figure(data=[*edge_traces, node_trace])
    fig.update_layout(
        title="Technique Relationship Graph",
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False},
        **_theme_layout(dark),
    )
    return fig.to_json()


def get_family_catalog() -> dict[str, dict]:
    """Return dictionary of all family metadata and variants for the UI detail drawer."""
    families = discover_families()
    catalog = {}
    for f in families:
        catalog[f.id] = {
            "id": f.id,
            "name": f.name,
            "category": f.category,
            "summary": f.summary,
            "mechanism": f.mechanism or "",
            "solves": list(f.solves),
            "complexity": f.implementation_complexity,
            "variants": [
                {
                    "id": v.id,
                    "name": v.name,
                    "summary": v.summary or "",
                    "complexity": v.implementation_complexity,
                }
                for v in f.variants
            ],
        }
    return catalog


def all_figures(
    parquet_path: str = "data/synthetic/scenarios.parquet",
    dark: bool = True,
) -> dict[str, str]:
    """Generate all insight figures as JSON strings."""
    return {
        "treemap": treemap_technique_frequency(parquet_path, dark),
        "industry_heatmap": heatmap_industry_savings(parquet_path, dark),
        "correlation": heatmap_correlation(parquet_path, dark),
        "bubble": bubble_growth_savings(parquet_path, dark),
        "graph": technique_graph_spec(dark),
    }
