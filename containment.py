"""
containment.py
---------------------------------
Given an outbreak-capable cluster (R0 > 1), find the SMALLEST set of
accounts to quarantine/block so that the remaining subgraph's R0 drops
below 1 (i.e. the outbreak becomes self-limiting instead of growing).

Approach: greedy removal by betweenness centrality. Nodes with high
betweenness are "bridges" connecting otherwise-separate parts of the
ring (often the coordinator device/account tying multiple merchants
together) -- removing them fragments the cluster far more efficiently
than removing high-degree nodes alone. This is the network-science
analog of "vaccinate the superspreaders first."

This module also prices the decision: it estimates the $ cost of
quarantining K accounts (merchant friction) against the $ loss avoided
by preventing projected further spread (using the SIR forecast), so the
recommendation is a business decision, not just a graph statistic.
"""

import networkx as nx
from sir_model import compute_cluster_r0, simulate_sir

MERCHANT_FRICTION_COST_PER_ACCOUNT = 15    # est. cost of a false-positive block/friction event ($)
AVG_FRAUD_TXN_VALUE = 120                  # est. avg value extracted per compromised account ($)


def find_min_containment_set(G: nx.Graph, cluster_nodes: set):
    """
    Greedily remove the highest-betweenness ("bridge"/superspreader) node
    from the cluster, recompute R0, repeat until R0 <= 1 (self-limiting)
    OR the cluster is fully dismantled (0 edges left -- R0 is
    definitionally 0 at that point).

    There is deliberately NO artificial cap on how many nodes this will
    remove: a partial containment set that still leaves R0 > 1 is not a
    real recommendation -- it's a false sense of safety. If the honest
    answer is "you need to remove all N accounts to fully contain this,"
    the function says so, and the caller (report / API) surfaces that
    plainly rather than silently truncating.

    Returns: (quarantine_list_in_order, r0_after_each_removal)
             r0_after_each_removal[0] is the R0 before any action.
             r0_after_each_removal[-1] is the final R0 achieved.
    """
    remaining = set(cluster_nodes)
    quarantine_order = []
    r0_trace = [compute_cluster_r0(G, remaining)]

    while r0_trace[-1] > 1.0:
        sub = G.subgraph(remaining)
        if sub.number_of_edges() == 0:
            break  # fully dismantled -- R0 is 0, nothing left to spread through
        centrality = nx.betweenness_centrality(sub, weight="weight")
        if not centrality or max(centrality.values()) == 0:
            # no more bridge structure -- fall back to highest weighted degree
            degrees = dict(sub.degree(weight="weight"))
            top_node = max(degrees, key=degrees.get)
        else:
            top_node = max(centrality, key=centrality.get)
        remaining.discard(top_node)
        quarantine_order.append(top_node)
        r0_trace.append(compute_cluster_r0(G, remaining))

    return quarantine_order, r0_trace


def containment_summary(cluster_size: int, quarantine_list: list, r0_trace: list) -> str:
    """Human-readable one-liner for the report/API -- makes explicit
    whether full containment (R0<=1) was actually reached."""
    achieved = r0_trace[-1] <= 1.0
    pct = round(100 * len(quarantine_list) / cluster_size, 1) if cluster_size else 0
    if achieved:
        return (f"Contained: quarantining {len(quarantine_list)}/{cluster_size} "
                f"accounts ({pct}%) drops R0 from {r0_trace[0]} to {r0_trace[-1]}.")
    return (f"NOT fully contained by targeted quarantine alone -- removed "
            f"{len(quarantine_list)}/{cluster_size} accounts, R0 only reaches "
            f"{r0_trace[-1]}. Recommend full cluster block + manual review.")


def estimate_intervention_roi(G: nx.Graph, cluster_nodes: set, quarantine_list: list,
                               projection_steps: int = 15):
    """
    Compares projected fraud loss WITHOUT intervention vs. WITH the
    recommended quarantine set applied from t=0, using the SIR forecast
    as the loss-projection engine.
    """
    seed = {n for n in cluster_nodes}  # worst case: assume all currently flagged as seed risk
    # NOTE: in the live demo we seed from only the confirmed nodes; kept
    # simple here as a standalone utility for the report.

    no_action = simulate_sir(G, seed_infected=seed, n_steps=projection_steps)
    with_action = simulate_sir(G, seed_infected=seed, n_steps=projection_steps,
                                removed_nodes=set(quarantine_list))

    # Use CUMULATIVE ever-infected count, not instantaneous "currently
    # infected" -- fraud losses don't reverse when an account is later
    # blocked, so total-ever-compromised is the number that actually
    # drives dollar loss.
    total_compromised_no_action = len(no_action[-1]["ever_infected_nodes"])
    total_compromised_with_action = len(with_action[-1]["ever_infected_nodes"])

    accounts_saved = total_compromised_no_action - total_compromised_with_action
    loss_avoided = accounts_saved * AVG_FRAUD_TXN_VALUE
    friction_cost = len(quarantine_list) * MERCHANT_FRICTION_COST_PER_ACCOUNT
    net_benefit = loss_avoided - friction_cost

    return {
        "total_compromised_no_action": total_compromised_no_action,
        "total_compromised_with_action": total_compromised_with_action,
        "accounts_saved_from_compromise": accounts_saved,
        "estimated_loss_avoided_usd": loss_avoided,
        "friction_cost_usd": friction_cost,
        "net_benefit_usd": net_benefit,
    }


if __name__ == "__main__":
    import pandas as pd
    from graph_builder import build_contact_graph
    from sir_model import cluster_report

    df = pd.read_csv("synthetic_transactions.csv")
    C = build_contact_graph(df)

    for c in cluster_report(C):
        if not c["outbreak_capable"]:
            continue
        q_list, r0_trace = find_min_containment_set(C, c["cluster_nodes"])
        roi = estimate_intervention_roi(C, c["cluster_nodes"], q_list)
        print(f"\nCluster (size={c['size']}, initial R0={c['r0']}, label={c['dominant_label']})")
        print(f"  Quarantine set (in priority order): {len(q_list)} accounts")
        print(f"  R0 trace after each removal: {r0_trace}")
        print(f"  ROI: {roi}")
