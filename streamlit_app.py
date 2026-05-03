"""Streamlit demo: visualize a research agent report.json."""
from __future__ import annotations
import json
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="Deep Research Agent Demo",
    page_icon="🔍",
    layout="wide",
)

SEVERITY_COLORS = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🟢",
}

CATEGORY_ICONS = {
    "REGULATORY": "⚖️",
    "REPUTATIONAL": "📰",
    "NETWORK": "🕸️",
    "FINANCIAL": "💰",
    "INCONSISTENCY": "⚠️",
    "COVERAGE_GAP": "🔍",
    "OTHER": "❓",
}


def load_report(source) -> dict | None:
    """Load report from uploaded file or path."""
    if source is None:
        return None
    try:
        if isinstance(source, (str, Path)):
            return json.loads(Path(source).read_text())
        else:
            return json.loads(source.read())
    except Exception as exc:
        st.error(f"Failed to load report: {exc}")
        return None


def render_header(report: dict) -> None:
    target = report.get("target", {})
    st.title(f"🔍 Research Report: {target.get('name', 'Unknown')}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Claims", report.get("claim_count", 0))
    col2.metric("Risk Flags", report.get("risk_flag_count", 0))
    budget = report.get("budget_used", {})
    col3.metric("Iterations", budget.get("used_iterations", "—"))
    col4.metric("Cost", f"${budget.get('used_dollars', 0):.2f}")

    if target.get("role") or target.get("organization"):
        st.caption(
            f"{target.get('role', '')} · {target.get('organization', '')} · {target.get('geographic_hint', '')}"
        )


def render_risk_flags(report: dict) -> None:
    flags = report.get("risk_flags", [])
    if not flags:
        st.info("No risk flags identified.")
        return

    # Group by category
    by_category: dict[str, list] = {}
    for flag in flags:
        cat = flag.get("type", "OTHER")
        by_category.setdefault(cat, []).append(flag)

    for category, cat_flags in by_category.items():
        icon = CATEGORY_ICONS.get(category, "❓")
        with st.expander(
            f"{icon} {category} ({len(cat_flags)} flag{'s' if len(cat_flags) > 1 else ''})",
            expanded=True,
        ):
            for flag in cat_flags:
                sev = flag.get("severity", "LOW")
                sev_icon = SEVERITY_COLORS.get(sev, "⚪")
                st.markdown(f"**{sev_icon} {sev}** — {flag.get('description', '')}")
                if flag.get("evidence_claim_ids"):
                    st.caption(f"Evidence: {', '.join(flag['evidence_claim_ids'][:3])}")
                if flag.get("justification"):
                    st.caption(f"Justification: {flag['justification']}")
                conf = flag.get("confidence", 0)
                st.progress(conf, text=f"Confidence: {conf:.0%}")
                st.divider()


def render_claims(report: dict) -> None:
    import pandas as pd

    claims = report.get("claims", [])
    if not claims:
        st.info("No validated claims.")
        return

    rows = []
    for c in claims:
        sources = c.get("supporting_sources", [])
        min_tier = min((s.get("tier", 4) for s in sources), default=4)
        rows.append(
            {
                "ID": c.get("id", "")[:8] + "...",
                "Subject": c.get("subject", ""),
                "Predicate": c.get("predicate", ""),
                "Object": c.get("object", ""),
                "Confidence": c.get("confidence", 0.0),
                "Best Tier": min_tier,
                "Sources": len(c.get("source_urls", [])),
            }
        )

    df = pd.DataFrame(rows)

    # Color confidence column
    st.dataframe(
        df.style.background_gradient(subset=["Confidence"], cmap="RdYlGn", vmin=0, vmax=1),
        use_container_width=True,
        hide_index=True,
    )


def render_graph(report: dict) -> None:
    entities = report.get("entities", [])
    relations = report.get("relations", [])

    if not entities:
        st.info("No identity graph data.")
        return

    try:
        import networkx as nx
        import plotly.graph_objects as go

        G = nx.DiGraph()
        entity_map = {e["id"]: e for e in entities}

        for e in entities:
            G.add_node(e["id"], label=e.get("canonical_name", ""), type=e.get("type", ""))

        for r in relations:
            G.add_edge(
                r["subject_entity_id"], r["object_entity_id"], label=r.get("predicate", "")
            )

        pos = nx.spring_layout(G, seed=42)

        node_x, node_y, node_text = [], [], []
        for node_id in G.nodes():
            x, y = pos[node_id]
            node_x.append(x)
            node_y.append(y)
            e = entity_map.get(node_id, {})
            node_text.append(f"{e.get('canonical_name', node_id)}<br>({e.get('type', '')})")

        edge_x, edge_y = [], []
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=edge_x,
                y=edge_y,
                mode="lines",
                line=dict(width=1, color="#888"),
                hoverinfo="none",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=node_x,
                y=node_y,
                mode="markers+text",
                text=[entity_map.get(n, {}).get("canonical_name", n) for n in G.nodes()],
                textposition="top center",
                marker=dict(size=12, color="#1f77b4"),
                hovertext=node_text,
                hoverinfo="text",
            )
        )
        fig.update_layout(
            showlegend=False,
            height=400,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
        st.plotly_chart(fig, use_container_width=True)

    except ImportError:
        # Fallback: simple text representation
        st.write(f"**{len(entities)} entities**, **{len(relations)} relations**")
        for e in entities[:10]:
            st.write(
                f"- **{e.get('canonical_name')}** ({e.get('type')}) — confidence: {e.get('confidence', 0):.2f}"
            )


def main() -> None:
    st.sidebar.title("Deep Research Agent")
    st.sidebar.markdown("Upload a `report.json` to visualize results.")

    # Load options
    input_method = st.sidebar.radio("Load report from:", ["File upload", "Run directory path"])

    report = None
    if input_method == "File upload":
        uploaded = st.sidebar.file_uploader("report.json", type="json")
        if uploaded:
            report = load_report(uploaded)
    else:
        run_path = st.sidebar.text_input("Path to run directory:", placeholder="runs/demo")
        if run_path:
            report_path = Path(run_path) / "report.json"
            if report_path.exists():
                report = load_report(report_path)
            else:
                st.sidebar.error(f"report.json not found in {run_path}")

    if report is None:
        st.markdown("""
        ## Welcome to the Deep Research Agent Demo

        Upload a `report.json` from a completed run to explore:
        - 📊 **Risk flags** grouped by category with severity ratings
        - 🔬 **Claim inventory** with confidence scores and source provenance
        - 🕸️ **Identity graph** showing entity relationships

        ### Quick Start
        ```bash
        python -m research_agent run --target "Elon Musk" --output runs/demo
        # Then upload runs/demo/report.json here
        ```
        """)
        return

    render_header(report)

    tab1, tab2, tab3 = st.tabs(["🚨 Risk Flags", "📋 Claims", "🕸️ Identity Graph"])

    with tab1:
        render_risk_flags(report)

    with tab2:
        render_claims(report)

    with tab3:
        render_graph(report)

    # Scope section at bottom
    st.markdown("---")
    st.caption(
        "⚠️ This system operates exclusively on public sources. "
        "No sensitive attributes were inferred. See report for full scope and limitations."
    )


if __name__ == "__main__":
    main()
