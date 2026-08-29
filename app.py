from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "demo_outputs" / "report.json"
CSV_PATH = ROOT / "synthetic_transactions.csv"

st.set_page_config(
    page_title="Outbreak Control Room",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    :root {
        --page-bg: #020817;
        --panel-bg: rgba(15, 23, 42, 0.92);
        --panel-strong: rgba(30, 41, 59, 0.96);
        --panel-soft: rgba(17, 24, 39, 0.9);
        --border: #334155;
        --text: #E2E8F0;
        --muted: #94A3B8;
        --white: #FFFFFF;
        --green: #22C55E;
        --red: #EF4444;
        --blue: #3B82F6;
        --purple: #8B5CF6;
        --amber: #F59E0B;
        --cyan: #67E8F9;
        --shadow: rgba(15, 23, 42, 0.8);
    }

    html, body, [data-testid="stAppViewContainer"] {
        background: var(--page-bg);
        color: var(--text);
        font-family: 'JetBrains Mono', monospace;
    }

    [data-testid="stSidebar"] {
        background: #0E1117 !important;
        border-right: 1px solid #334155 !important;
    }

    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stNumberInput label,
    [data-testid="stSidebar"] .stTextInput label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] button {
        color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] .stSlider [data-baseweb="slider"] {
        background: #1E293B !important;
    }

    [data-testid="stSidebar"] [data-baseweb="input"] {
        background: #1E293B !important;
        color: #FFFFFF !important;
        border: 1px solid #475569 !important;
    }

    [data-testid="stSidebar"] [data-baseweb="slider"] {
        background: #1E293B !important;
    }

    [data-testid="stSidebar"] .stSlider [data-testid="stBaseSliderThumb"] {
        background: #38BDF8 !important;
        border-color: #38BDF8 !important;
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    .header-shell {
        background: linear-gradient(180deg, rgba(15,23,42,0.96), rgba(15,23,42,0.82));
        border: 1px solid var(--border);
        border-radius: 14px;
        box-shadow: 0 0 22px rgba(15, 23, 42, 0.75);
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }

    .header-kicker {
        color: #00E5FF;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.32rem;
        text-transform: uppercase;
    }

    .header-title {
        margin-top: 0.25rem;
        color: var(--white);
        font-size: clamp(1.75rem, 2.2vw, 2.9rem);
        font-weight: 800;
        letter-spacing: 0.14rem;
        text-transform: uppercase;
    }

    .status-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin-top: 0.7rem;
    }

    .status-pill {
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid var(--border);
        border-radius: 999px;
        color: var(--text);
        padding: 0.34rem 0.7rem;
        font-size: 0.68rem;
        letter-spacing: 0.16rem;
        text-transform: uppercase;
    }

    .metric-card {
        background: var(--panel-strong);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.7rem 0.85rem;
        min-height: 90px;
        box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.08);
    }

    [data-testid="stMetricContainer"] > div {
        background: var(--panel-soft) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        padding: 0.75rem 0.85rem !important;
    }

    [data-testid="stMetricLabel"] {
        font-family: 'JetBrains Mono', monospace !important;
        text-transform: uppercase !important;
        letter-spacing: 0.12rem !important;
        color: var(--white) !important;
        font-size: 0.68rem !important;
        font-weight: 700 !important;
    }

    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        font-size: 1.7rem !important;
    }

    .metric-green { color: var(--green) !important; }
    .metric-red { color: var(--red) !important; }
    .metric-blue { color: var(--blue) !important; }
    .metric-amber { color: var(--amber) !important; }
    .metric-white { color: var(--white) !important; }

    .section-label {
        color: var(--white);
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.20rem;
        text-transform: uppercase;
        margin-top: 1.3rem;
        margin-bottom: 0.7rem;
    }

    .stSlider label {
        color: var(--white) !important;
        font-family: 'JetBrains Mono', monospace !important;
        letter-spacing: 0.16rem !important;
        text-transform: uppercase !important;
        font-size: 0.7rem !important;
    }

    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid var(--border);
    }

    .stDataFrame table {
        font-family: 'JetBrains Mono', monospace; 
        background: rgba(15, 23, 42, 0.9);
    }

    .stTabs [role="tablist"] {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid var(--border);
        border-radius: 12px;
    }

    .stTabs [role="tab"] {
        color: var(--white);
        font-family: 'JetBrains Mono', monospace;
        text-transform: uppercase;
        letter-spacing: 0.12rem;
    }

    .stPlotlyChart {
        background: rgba(2, 8, 23, 1);
        border: 1px solid var(--border);
        border-radius: 12px;
    }

    .summary-card {
        background: rgba(17, 24, 39, 0.96);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.8rem 0.9rem;
        min-height: 110px;
        box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.1);
    }

    .summary-label {
        color: #F8FAFC;
        font-size: 0.68rem;
        letter-spacing: 0.12rem;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
        font-weight: 700;
    }

    .summary-value {
        font-size: 1.8rem;
        line-height: 1.2;
        font-weight: 800;
        color: #FFFFFF;
    }

    .summary-amber { color: #F59E0B !important; }
    .summary-green { color: #38BDF8 !important; }
    .summary-red { color: #FFFFFF !important; }
    .summary-blue { color: #38BDF8 !important; }

    .terminal-note {
        color: var(--muted);
        font-size: 0.78rem;
        letter-spacing: 0.12rem;
        text-transform: uppercase;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


COLOR_MAP = {
    "Susceptible": "#22C55E",
    "Infected": "#EF4444",
    "Contained": "#3B82F6",
}


@st.cache_data
def load_data():
    df = pd.read_csv(CSV_PATH)
    with REPORT_PATH.open("r", encoding="utf-8") as fh:
        report = json.load(fh)

    cluster_df = pd.DataFrame(report)
    if "outbreak_capable" not in cluster_df.columns:
        cluster_df["outbreak_capable"] = False
    cluster_df["outbreak_capable"] = cluster_df["outbreak_capable"].fillna(False).astype(bool)

    if "roi" not in cluster_df.columns:
        cluster_df["roi"] = [{} for _ in range(len(cluster_df))]
    cluster_df["roi"] = cluster_df["roi"].apply(lambda x: x if isinstance(x, dict) else {})

    cluster_df["net_benefit_usd"] = cluster_df["roi"].apply(
        lambda x: x.get("net_benefit_usd", 0) if isinstance(x, dict) else 0
    )
    cluster_df["loss_avoided_usd"] = cluster_df["roi"].apply(
        lambda x: x.get("estimated_loss_avoided_usd", 0) if isinstance(x, dict) else 0
    )
    cluster_df["friction_cost_usd"] = cluster_df["roi"].apply(
        lambda x: x.get("friction_cost_usd", 0) if isinstance(x, dict) else 0
    )

    if "quarantine_accounts" not in cluster_df.columns:
        cluster_df["quarantine_accounts"] = [[] for _ in range(len(cluster_df))]
    cluster_df["quarantine_count"] = cluster_df["quarantine_accounts"].apply(
        lambda x: len(x) if isinstance(x, list) else 0
    )

    outbreak_df = cluster_df[cluster_df["outbreak_capable"]].copy()
    label_counts = df["label"].value_counts().sort_index()
    return df, cluster_df, outbreak_df, label_counts


@st.cache_data
def build_cluster_network(df):
    suspicious = ["syndicate_1", "syndicate_0", "syndicate_2"]
    cluster_map = {}
    for label in suspicious:
        accounts = df[df["label"] == label]["account"].drop_duplicates().tolist()
        cluster_map[label] = accounts

    positions = {
        "syndicate_1": (0.0, 0.0),
        "syndicate_0": (3.2, 1.6),
        "syndicate_2": (-3.2, 1.6),
    }

    node_positions = {}
    edges = []

    for label, accounts in cluster_map.items():
        cx, cy = positions[label]
        count = max(1, len(accounts))
        for idx, account in enumerate(accounts):
            angle = (2 * math.pi * idx) / count
            x = cx + 0.9 * math.cos(angle)
            y = cy + 0.9 * math.sin(angle)
            node_positions[account] = (x, y)

        for idx in range(len(accounts)):
            a = accounts[idx]
            b = accounts[(idx + 1) % len(accounts)]
            edges.append((a, b))

    if len(cluster_map.get("syndicate_1", [])) > 0 and len(cluster_map.get("syndicate_0", [])) > 0:
        edges.append((cluster_map["syndicate_1"][0], cluster_map["syndicate_0"][0]))
    if len(cluster_map.get("syndicate_1", [])) > 0 and len(cluster_map.get("syndicate_2", [])) > 0:
        edges.append((cluster_map["syndicate_1"][1], cluster_map["syndicate_2"][1]))
    if len(cluster_map.get("syndicate_0", [])) > 0 and len(cluster_map.get("syndicate_2", [])) > 0:
        edges.append((cluster_map["syndicate_0"][1], cluster_map["syndicate_2"][0]))

    return cluster_map, node_positions, edges


@st.cache_data
def build_timeline(cluster_map):
    all_accounts = []
    for accounts in cluster_map.values():
        all_accounts.extend(accounts)

    timeline = []
    for step in range(6):
        states = {account: "Susceptible" for account in all_accounts}
        if step == 0:
            infect_targets = all_accounts[:3]
        elif step == 1:
            infect_targets = all_accounts[:5]
        elif step == 2:
            infect_targets = all_accounts[:7]
        elif step == 3:
            infect_targets = all_accounts[:9]
        elif step == 4:
            infect_targets = all_accounts[:9]
        else:
            infect_targets = all_accounts[:8]

        for account in infect_targets:
            states[account] = "Infected"

        if step >= 3:
            for idx in range(0, 5):
                states[all_accounts[idx]] = "Contained"
        if step >= 4:
            for idx in range(6, 10):
                states[all_accounts[idx]] = "Infected"

        timeline.append(states)
    return timeline


def render_metric(label: str, value: str, accent_class: str):
    st.markdown(
        f"""
        <div class='metric-card'>
            <div style='color: #FFFFFF; font-size: 0.68rem; letter-spacing: 0.12rem; text-transform: uppercase; margin-bottom: 0.35rem;'>{label}</div>
            <div class='metric-value {accent_class}' style='font-size: 1.8rem; font-weight: 800; line-height: 1.2;'>{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary_metric(label: str, value: str, accent_class: str):
    st.markdown(
        f"""
        <div class='summary-card'>
            <div class='summary-label'>{label}</div>
            <div class='summary-value {accent_class}'>{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def dark_bar_chart(series, title):
    fig = go.Figure(data=[go.Bar(
        x=list(series.index),
        y=list(series.values),
        marker=dict(color=["#22C55E", "#EF4444", "#3B82F6", "#F59E0B"][: len(series)], line=dict(color="#E2E8F0", width=1.0)),
        text=list(series.values),
        textposition="outside",
        hovertemplate="%{{x}}: %{{y}}<extra></extra>",
    )])
    fig.update_layout(
        title=title,
        title_font=dict(size=12, family="JetBrains Mono, monospace", color="#F8FAFC"),
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        font=dict(color="#F8FAFC", family="JetBrains Mono, monospace"),
        margin=dict(l=18, r=18, t=36, b=18),
        bargap=0.3,
        xaxis=dict(
            tickfont=dict(size=10, color="#F8FAFC"),
            showgrid=False,
            zeroline=False,
            title_font=dict(color="#F8FAFC"),
        ),
        yaxis=dict(
            tickfont=dict(size=10, color="#F8FAFC"),
            showgrid=True,
            gridcolor="rgba(148,163,184,0.2)",
            zeroline=False,
            title_font=dict(color="#F8FAFC"),
        ),
    )
    return fig


df, cluster_df, outbreak_df, label_counts = load_data()
cluster_map, node_positions, edges = build_cluster_network(df)
timeline = build_timeline(cluster_map)

st.sidebar.title("Scenario Controls")
avg_loss = st.sidebar.slider("Average Fraud Loss ($)", min_value=0, max_value=5000, value=120, step=10)
friction_cost = st.sidebar.slider("Customer Friction Cost per Interruption ($)", min_value=0, max_value=500, value=15, step=5)

st.markdown(
    """
    <div class='header-shell'>
        <div class='header-kicker'>Razorpay AI Buildathon // track 02</div>
        <div class='header-title'>OUTBREAK CONTROL ROOM</div>
        <div class='status-row'>
            <div class='status-pill'>SYSTEM: LIVE</div>
            <div class='status-pill'>MODEL: SIR / R0 FORECAST</div>
            <div class='status-pill'>GREY ZONE: 133 CLUSTERS</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

scrubber_step = st.slider(
    "DRAG TO ADVANCE TIME",
    min_value=0,
    max_value=len(timeline) - 1,
    value=0,
    step=1,
    key="timeline_slider",
    help="Susceptible -> Infected -> Contained",
)

current_snapshot = timeline[scrubber_step]
counts = {"Susceptible": 0, "Infected": 0, "Contained": 0}
for state in current_snapshot.values():
    counts[state] = counts.get(state, 0) + 1

metric_cols = st.columns(4)
with metric_cols[0]:
    render_metric("SUSCEPTIBLE", str(counts["Susceptible"]), "metric-green")
with metric_cols[1]:
    render_metric("INFECTED", str(counts["Infected"]), "metric-red")
with metric_cols[2]:
    render_metric("CONTAINED", str(counts["Contained"]), "metric-blue")
with metric_cols[3]:
    render_metric("R0 PEAK", f"{cluster_df['r0'].max():.2f}", "metric-amber")

cluster_filter = st.selectbox(
    "Cluster Filter",
    options=["All Clusters", "Syndicate 0", "Syndicate 1", "Syndicate 2"],
    index=0,
    help="Filter the network view to a specific syndicate cluster.",
)

st.markdown("<div class='section-label'>NETWORK PROPAGATION VIEW</div>", unsafe_allow_html=True)

selected_cluster = None if cluster_filter == "All Clusters" else cluster_filter.lower().replace(" ", "_")

node_x, node_y, node_color, node_text, node_hover = [], [], [], [], []
for account, (x, y) in node_positions.items():
    cluster_name = None
    for label, members in cluster_map.items():
        if account in members:
            cluster_name = label
            break
    if selected_cluster is not None and cluster_name != selected_cluster:
        continue
    state = current_snapshot.get(account, "Susceptible")
    node_x.append(x)
    node_y.append(y)
    node_color.append(COLOR_MAP[state])
    node_text.append(account)
    node_hover.append(f"Account: {account}<br>State: {state}<br>Cluster: {cluster_name}")

edge_x, edge_y = [], []
for a, b in edges:
    if a in node_positions and b in node_positions:
        if selected_cluster is not None:
            a_cluster = None
            b_cluster = None
            for label, members in cluster_map.items():
                if a in members:
                    a_cluster = label
                if b in members:
                    b_cluster = label
            if a_cluster != selected_cluster or b_cluster != selected_cluster:
                continue
        x1, y1 = node_positions[a]
        x2, y2 = node_positions[b]
        edge_x.extend([x1, x2, None])
        edge_y.extend([y1, y2, None])

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(color="rgba(148, 163, 184, 0.9)", width=1.8),
        hoverinfo="skip",
        showlegend=False,
    )
)
fig.add_trace(
    go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
    text=[label[:8] + "..." if len(label) > 11 else label for label in node_text],
        textposition="top center",
    textfont=dict(color="#E2E8F0", size=8),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=node_hover,
        marker=dict(
            size=18,
            color=node_color,
            line=dict(color="#F8FAFC", width=1.2),
            opacity=0.96,
        ),
        showlegend=False,
    )
)
fig.update_layout(
    paper_bgcolor="#020817",
    plot_bgcolor="#020817",
    margin=dict(l=12, r=12, t=12, b=12),
    height=520,
    font=dict(color="#E2E8F0", family="JetBrains Mono, monospace"),
    xaxis=dict(showgrid=False, visible=False, zeroline=False, range=[-4.5, 4.5]),
    yaxis=dict(showgrid=False, visible=False, zeroline=False, range=[-3.2, 3.2]),
)

st.plotly_chart(fig, use_container_width=True, key="network_plot")

st.markdown("<div class='section-label'>Threat Signal Summary</div>", unsafe_allow_html=True)
summary_cols = st.columns(3)
with summary_cols[0]:
    render_summary_metric("MAX R0", f"{cluster_df['r0'].max():.2f}", "summary-amber")
with summary_cols[1]:
    render_summary_metric("AVG NON-OUTBREAK R0", f"{cluster_df[~cluster_df['outbreak_capable']]['r0'].mean():.2f}", "summary-green")
with summary_cols[2]:
    render_summary_metric("RESPONSE ACTIONS", f"{outbreak_df['quarantine_count'].sum():,}", "summary-blue")

st.markdown("<div class='section-label'>Label Distribution</div>", unsafe_allow_html=True)
bar_cols = st.columns(2)
with bar_cols[0]:
    st.plotly_chart(dark_bar_chart(label_counts, "LABEL DISTRIBUTION"), use_container_width=True)
with bar_cols[1]:
    risk_chart = outbreak_df[["dominant_label", "r0"]].copy()
    risk_chart = risk_chart.rename(columns={"dominant_label": "risk_group"})
    st.plotly_chart(dark_bar_chart(risk_chart.set_index("risk_group")["r0"], "R0 BY RISK GROUP"), use_container_width=True)

st.markdown("<div class='section-label'>Cluster Response Table</div>", unsafe_allow_html=True)
if outbreak_df.empty:
    st.warning("No outbreak-capable clusters detected in the current snapshot.")
else:
    table = outbreak_df[[
        "dominant_label",
        "cluster_size",
        "r0",
        "quarantine_count",
        "roi",
    ]].copy()
    table["accounts_saved"] = table.apply(
        lambda row: row["roi"].get("accounts_saved_from_compromise") if isinstance(row["roi"], dict) and "accounts_saved_from_compromise" in row["roi"] else max(0, row["cluster_size"] - 1),
        axis=1,
    )
    table["Loss avoided ($)"] = (table["accounts_saved"] * avg_loss).round(2)
    table["Friction ($)"] = (table["quarantine_count"] * friction_cost).round(2)
    table["Net benefit ($)"] = (table["Loss avoided ($)"] - table["Friction ($)"]).round(2)
    table = table.rename(columns={
        "dominant_label": "Cluster",
        "cluster_size": "Size",
        "r0": "R0",
        "quarantine_count": "Quarantined",
    })
    table = table[["Cluster", "Size", "R0", "Quarantined", "Loss avoided ($)", "Friction ($)", "Net benefit ($)"]]
    st.dataframe(table.sort_values("R0", ascending=False), use_container_width=True, hide_index=True)

st.caption(f"LIVE STEP: T{scrubber_step} | SUSCEPTIBLE={counts['Susceptible']} | INFECTED={counts['Infected']} | CONTAINED={counts['Contained']}")
st.caption("Source data: synthetic_transactions.csv and demo_outputs/report.json")
