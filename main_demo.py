"""
main_demo.py
---------------------------------
THE single script that produces every output you need for the pitch:
  - console report (R0 per cluster, containment sets, ROI)
  - audit_trail.db populated with every decision
  - report.json (machine-readable full results)
  - 4 PNG visualizations for the demo/pitch deck:
        1. contact_graph_overview.png   -- whole graph, clusters colour-coded
        2. outbreak_spread_snapshots.png -- infection spreading over time (no action)
        3. containment_comparison.png    -- infection curve WITH vs WITHOUT containment
        4. r0_by_cluster.png             -- bar chart of R0 per cluster

Run:
    python generate_synthetic_data.py   # only needed once / to regenerate data
    python main_demo.py
"""

import json
import os
import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd

from graph_builder import build_contact_graph, build_heterogeneous_graph
from sir_model import simulate_sir, cluster_report, GAMMA, GLOBAL_BETA_SCALE
from containment import find_min_containment_set, estimate_intervention_roi, containment_summary
import audit_trail

OUT_DIR = "demo_outputs"
os.makedirs(OUT_DIR, exist_ok=True)


def run_pipeline():
    print("=" * 70)
    print("OUTBREAK GUARD -- Cross-Merchant Fraud Epidemic Risk Engine")
    print("=" * 70)

    # 1. Data
    df = pd.read_csv("synthetic_transactions.csv")
    print(f"\n[1/6] Loaded {len(df)} synthetic transactions across "
          f"{df['merchant'].nunique()} merchants.")

    # 2. Graphs
    hetero = build_heterogeneous_graph(df)
    C = build_contact_graph(df)
    print(f"[2/6] Built heterogeneous graph "
          f"({hetero.number_of_nodes()} nodes, {hetero.number_of_edges()} edges) "
          f"and collapsed contact graph "
          f"({C.number_of_nodes()} nodes, {C.number_of_edges()} edges).")

    # 3. Cluster / R0 report
    clusters = cluster_report(C)
    outbreak_clusters = [c for c in clusters if c["outbreak_capable"]]
    safe_clusters = [c for c in clusters if not c["outbreak_capable"]]
    print(f"[3/6] Found {len(clusters)} multi-account clusters. "
          f"{len(outbreak_clusters)} are outbreak-capable (R0 > 1).")
    for c in outbreak_clusters:
        print(f"       [OUTBREAK-CAPABLE] size={c['size']:>3}  R0={c['r0']:>6}  "
              f"dominant_label={c['dominant_label']}")
    if safe_clusters:
        avg_r0 = sum(c["r0"] for c in safe_clusters) / len(safe_clusters)
        print(f"       [self-contained]   {len(safe_clusters)} other clusters "
              f"(mostly ordinary shared-IP noise, avg R0={avg_r0:.2f}) -- "
              f"correctly NOT flagged as outbreak risk")

    # 4. Containment + ROI for outbreak-capable clusters, log every decision
    conn = audit_trail.init_db()
    full_results = []
    print("\n[4/6] Running containment simulation + audit logging...")
    for c in clusters:
        if c["outbreak_capable"]:
            q_list, r0_trace = find_min_containment_set(C, c["cluster_nodes"])
            roi = estimate_intervention_roi(C, c["cluster_nodes"], q_list)
            audit_trail.log_decision(conn, c, q_list, r0_trace, roi)
            print(f"       Cluster (size={c['size']}, R0={c['r0']}): "
                  f"{containment_summary(c['size'], q_list, r0_trace)} "
                  f"Net benefit: ${roi['net_benefit_usd']:.0f}")
        else:
            q_list, r0_trace, roi = [], [c["r0"]], {}
            audit_trail.log_decision(conn, c, q_list, r0_trace, roi)
        full_results.append({"cluster": c, "quarantine": q_list, "r0_trace": r0_trace, "roi": roi})

    # 5. Save machine-readable report
    serializable = []
    for r in full_results:
        c = r["cluster"]
        serializable.append({
            "cluster_size": c["size"],
            "r0": c["r0"],
            "outbreak_capable": c["outbreak_capable"],
            "dominant_label": c["dominant_label"],
            "quarantine_accounts": r["quarantine"],
            "r0_trace_after_containment": r["r0_trace"],
            "roi": r["roi"],
        })
    with open(os.path.join(OUT_DIR, "report.json"), "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\n[5/6] Wrote machine-readable report -> {OUT_DIR}/report.json")

    # 6. Visualizations
    print(f"[6/6] Generating visualizations into {OUT_DIR}/ ...")
    plot_contact_graph_overview(C, clusters)
    biggest_outbreak = max((c for c in clusters if c["outbreak_capable"]),
                            key=lambda c: c["r0"], default=None)
    if biggest_outbreak:
        plot_outbreak_spread_snapshots(C, biggest_outbreak)
        matching = next(r for r in full_results if r["cluster"] is biggest_outbreak)
        plot_containment_comparison(C, biggest_outbreak, matching["quarantine"])
    plot_r0_by_cluster(clusters)

    print("\nDone. All outputs are in the demo_outputs/ folder.")
    return full_results, clusters


# ---------------------------------------------------------------- plots ---

def _cluster_color_map(clusters):
    palette = ["#e63946", "#f4a261", "#2a9d8f", "#264653", "#8338ec", "#ff006e"]
    node_color = {}
    for i, c in enumerate(clusters):
        color = palette[i % len(palette)] if c["outbreak_capable"] else "#adb5bd"
        for n in c["cluster_nodes"]:
            node_color[n] = color
    return node_color


def plot_contact_graph_overview(C, clusters):
    node_color_map = _cluster_color_map(clusters)
    colors = [node_color_map.get(n, "#dee2e6") for n in C.nodes()]
    sizes = [40 if n in node_color_map else 10 for n in C.nodes()]

    plt.figure(figsize=(10, 8))
    pos = nx.spring_layout(C, seed=42, k=0.35)
    nx.draw_networkx_edges(C, pos, alpha=0.15, width=0.6)
    nx.draw_networkx_nodes(C, pos, node_color=colors, node_size=sizes, linewidths=0)
    plt.title("Cross-Merchant Contact Graph\n(red/orange/teal = outbreak-capable syndicate "
              "clusters, grey = isolated/legit accounts)", fontsize=11)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "contact_graph_overview.png"), dpi=150)
    plt.close()


def plot_outbreak_spread_snapshots(C, cluster, n_steps=15):
    """
    Colors reflect CUMULATIVE exposure, not just instantaneous state:
      teal  = still untouched (Susceptible)
      red   = currently active infection (I)
      purple = was infected at some point, since recovered/blocked (R)
               -- still counts as a compromised account (fraud already
               happened) even though it's no longer "active"
    This avoids the misleading impression that a shrinking red count
    means the damage is undone -- purple nodes are still losses.
    """
    seed = set(list(cluster["cluster_nodes"])[:2])  # start from 2 "patient zero" accounts
    history = simulate_sir(C, seed_infected=seed, n_steps=n_steps)
    snapshot_ts = [0, n_steps // 3, (2 * n_steps) // 3, n_steps - 1]

    sub_nodes = cluster["cluster_nodes"]
    sub = C.subgraph(sub_nodes)
    pos = nx.spring_layout(sub, seed=42)

    fig, axes = plt.subplots(1, len(snapshot_ts), figsize=(18, 4.5))
    for ax, t in zip(axes, snapshot_ts):
        infected_now = history[t]["infected_nodes"]
        ever_infected = history[t]["ever_infected_nodes"]
        colors = []
        for n in sub.nodes():
            if n in infected_now:
                colors.append("#e63946")       # active
            elif n in ever_infected:
                colors.append("#8338ec")       # recovered/blocked, still a loss
            else:
                colors.append("#a8dadc")       # untouched
        nx.draw_networkx_edges(sub, pos, ax=ax, alpha=0.3, width=0.8)
        nx.draw_networkx_nodes(sub, pos, ax=ax, node_color=colors, node_size=120, linewidths=0.5,
                                edgecolors="black")
        ax.set_title(f"t = {t}\nactive: {len(infected_now)}  |  "
                     f"ever-compromised: {len(ever_infected)}/{len(sub.nodes())}", fontsize=9)
        ax.axis("off")
    fig.suptitle(f"Outbreak Spread Over Time -- Cluster R0={cluster['r0']} (no intervention)\n"
                 f"red = actively infected now, purple = compromised earlier "
                 f"(already a fraud loss even if since blocked), teal = untouched",
                 fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "outbreak_spread_snapshots.png"), dpi=150)
    plt.close()


def plot_containment_comparison(C, cluster, quarantine_list, n_steps=15):
    """
    Plots CUMULATIVE ever-compromised accounts over time -- this is the
    curve that actually matters for fraud loss, since it only ever goes
    up (an account that's later blocked was still used for fraud first).
    This is deliberately different from a textbook "active infections"
    SIR curve, which can misleadingly shrink back to zero on a small
    graph even without any intervention, purely from natural recovery.

    Seed ("patient zero") is deliberately chosen OUTSIDE the recommended
    quarantine set. Assuming containment happens to catch patient zero
    itself before any infection starts would be an unrealistically best
    -case setup -- the realistic scenario is that an attacker enters
    through a peripheral account, and containment works by removing the
    high-betweenness bridge/coordinator accounts BEFORE the infection
    can reach and spread through them, not by psychically pre-blocking
    the exact entry point.
    """
    non_quarantined = list(cluster["cluster_nodes"] - set(quarantine_list))
    seed_pool = non_quarantined if non_quarantined else list(cluster["cluster_nodes"])
    seed = set(seed_pool[:2])

    no_action = simulate_sir(C, seed_infected=seed, n_steps=n_steps)
    with_action = simulate_sir(C, seed_infected=seed, n_steps=n_steps,
                                removed_nodes=set(quarantine_list))

    t = [h["t"] for h in no_action]
    cumulative_no_action = [len(h["ever_infected_nodes"]) for h in no_action]
    cumulative_with_action = [len(h["ever_infected_nodes"]) for h in with_action]

    plt.figure(figsize=(8, 5.5))
    plt.plot(t, cumulative_no_action, marker="o", color="#e63946",
              label="No intervention (cumulative accounts compromised)")
    plt.plot(t, cumulative_with_action, marker="o", color="#2a9d8f",
              label=f"With containment ({len(quarantine_list)} accounts pre-quarantined)")
    plt.xlabel("Time step")
    plt.ylabel("Cumulative accounts ever compromised")
    plt.title(f"Containment Impact -- Cluster R0={cluster['r0']}\n"
              f"Quarantining {len(quarantine_list)} high-betweenness accounts "
              f"caps total accounts that can ever be compromised")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "containment_comparison.png"), dpi=150)
    plt.close()


def plot_r0_by_cluster(clusters):
    """
    Show every outbreak-capable cluster individually (there are only a
    handful -- these are the interesting cases), but collapse the many
    small self-contained "noise" clusters (e.g. ordinary household/office
    IP-sharing) into a single summary bar. Plotting all ~130+ of them
    individually would make the chart unreadable and would bury the
    actual signal -- exactly the "isolated view looks normal" blindness
    problem this project exists to solve, so the chart shouldn't
    recreate it.
    """
    outbreak = [c for c in clusters if c["outbreak_capable"]]
    safe = [c for c in clusters if not c["outbreak_capable"]]

    labels = [f"Ring {i+1}\n(n={c['size']}, {c['dominant_label']})"
              for i, c in enumerate(outbreak)]
    r0s = [c["r0"] for c in outbreak]
    colors = ["#e63946"] * len(outbreak)

    if safe:
        avg_safe_r0 = sum(c["r0"] for c in safe) / len(safe)
        labels.append(f"{len(safe)} other clusters\n(legit noise, avg)")
        r0s.append(round(avg_safe_r0, 2))
        colors.append("#2a9d8f")

    plt.figure(figsize=(8, 5.5))
    bars = plt.bar(labels, r0s, color=colors)
    plt.axhline(1.0, color="black", linestyle="--", linewidth=1, label="R0 = 1 (outbreak threshold)")
    plt.ylabel("R0 (reproduction number)")
    plt.title("Reproduction Number: Detected Syndicate Rings\nvs. Ordinary Multi-Account Clusters")
    plt.xticks(fontsize=8)
    plt.legend()
    for bar, r0 in zip(bars, r0s):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                  str(r0), ha="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "r0_by_cluster.png"), dpi=150)
    plt.close()


if __name__ == "__main__":
    run_pipeline()
