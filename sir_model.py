"""
sir_model.py
---------------------------------
Discrete-time, edge-weighted SIR simulation over the account contact graph.

States:
  S (Susceptible) - legitimate, not yet compromised
  I (Infected)     - actively compromised / confirmed fraud
  R (Removed)      - either detected+blocked by existing systems, or
                      quarantined by our containment engine

Per time step, each Infected node attempts to "infect" each Susceptible
neighbor with probability = edge weight * GLOBAL_BETA_SCALE (this is the
weighted transmission rate -- shared device edges transmit far more
readily than shared-subnet edges, see graph_builder.py).

Each Infected node recovers (gets removed) with probability GAMMA per
step, standing in for "how fast would Razorpay's existing detection
systems eventually catch and block this account anyway." This keeps the
number honest: we are modeling incremental risk ON TOP OF existing
detection, not pretending nothing else is watching.

R0 is computed per connected component (cluster) using the standard
approximation for network SIR:
    R0 ~= (beta / gamma) * <k>
where <k> is the average degree within that cluster and beta is the
average edge weight in the cluster (since weight already encodes
transmission probability, beta IS effectively the weighted degree, so we
compute it directly from the graph rather than assuming a uniform beta).

Clusters with R0 > 1 are self-sustaining outbreaks (will keep growing
without intervention); R0 < 1 clusters burn out on their own.
"""

import random
import networkx as nx

GAMMA = 0.2           # per-step recovery/detection probability -- calibrated
                       # against real cluster diagnostics (see calibrate.py) so
                       # that weak, single-signal legit clusters (R0 < 1, self
                       # -contained) are clearly separated from real multi
                       # -signal syndicate rings (R0 > 1, outbreak-capable)
GLOBAL_BETA_SCALE = 1.0  # multiplier applied to edge weights -> effective beta
random.seed(7)


def compute_cluster_r0(G: nx.Graph, nodes: set) -> float:
    """R0 = (avg edge weight / gamma) * avg degree, computed on the
    induced subgraph for this cluster."""
    sub = G.subgraph(nodes)
    if sub.number_of_edges() == 0:
        return 0.0
    avg_weight = sum(d["weight"] for _, _, d in sub.edges(data=True)) / sub.number_of_edges()
    avg_degree = (2 * sub.number_of_edges()) / sub.number_of_nodes()
    beta = avg_weight * GLOBAL_BETA_SCALE
    return round((beta / GAMMA) * avg_degree, 2)


def simulate_sir(G: nx.Graph, seed_infected: set, n_steps: int = 15,
                  removed_nodes: set = None):
    """
    Run the simulation forward n_steps.

    States are S / I / R / Q, kept distinct on purpose:
      Q = pre-quarantined by our containment engine BEFORE the outbreak
          reached them -- these accounts are never infected, full stop.
      R = recovered/blocked AFTER having been infected -- i.e. fraud
          already happened on that account before it was caught.
    Collapsing Q and R into one "removed" bucket (as a textbook SIR model
    would) hides the point of running this in the first place: a
    quarantined account costs nothing in fraud losses, a recovered one
    already did. We track "ever_infected" (I ever entered, regardless of
    whether it has since moved to R) as the cumulative-loss-relevant
    number -- this is what the containment ROI should be computed from,
    not the instantaneous "currently infected" count, since fraud losses
    don't reverse just because an account later gets blocked.

    removed_nodes: nodes pre-quarantined at t=0 (state Q) -- this is how
    the containment engine tests "what if we blocked these accounts
    before the outbreak started."

    Returns a list of dicts, one per time step:
      {"t", "S", "I", "R", "Q", "infected_nodes" (currently I),
       "ever_infected_nodes" (cumulative, I ever entered)}
    """
    removed_nodes = removed_nodes or set()
    state = {}
    for n in G.nodes():
        if n in removed_nodes:
            state[n] = "Q"
        elif n in seed_infected:
            state[n] = "I"
        else:
            state[n] = "S"

    ever_infected = set(seed_infected) - removed_nodes

    history = []
    for t in range(n_steps):
        counts = {"S": 0, "I": 0, "R": 0, "Q": 0}
        for s in state.values():
            counts[s] += 1
        infected_now = {n for n, s in state.items() if s == "I"}
        history.append({
            "t": t, **counts,
            "infected_nodes": set(infected_now),
            "ever_infected_nodes": set(ever_infected),
        })

        new_state = dict(state)
        for node in infected_now:
            # attempt to infect susceptible neighbors
            for neighbor in G.neighbors(node):
                if state[neighbor] == "S":
                    p_infect = G[node][neighbor]["weight"] * GLOBAL_BETA_SCALE
                    if random.random() < p_infect:
                        new_state[neighbor] = "I"
                        ever_infected.add(neighbor)
            # attempt recovery/removal
            if random.random() < GAMMA:
                new_state[node] = "R"
        state = new_state

    return history


def cluster_report(G: nx.Graph, min_size: int = 2):
    """Compute R0 for every connected component of size >= min_size."""
    report = []
    for comp in nx.connected_components(G):
        if len(comp) < min_size:
            continue
        r0 = compute_cluster_r0(G, comp)
        labels = [G.nodes[n].get("label", "unknown") for n in comp]
        report.append({
            "cluster_nodes": comp,
            "size": len(comp),
            "r0": r0,
            "outbreak_capable": r0 > 1.0,
            "dominant_label": max(set(labels), key=labels.count),
        })
    return sorted(report, key=lambda x: x["r0"], reverse=True)


if __name__ == "__main__":
    import pandas as pd
    from graph_builder import build_contact_graph

    df = pd.read_csv("synthetic_transactions.csv")
    C = build_contact_graph(df)

    print("\n=== Cluster R0 Report ===")
    for c in cluster_report(C):
        flag = "OUTBREAK-CAPABLE" if c["outbreak_capable"] else "self-contained"
        print(f"size={c['size']:>3}  R0={c['r0']:>5}  [{flag}]  dominant_label={c['dominant_label']}")
