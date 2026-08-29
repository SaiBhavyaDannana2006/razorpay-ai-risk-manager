"""
graph_builder.py
---------------------------------
Two graphs are built from the same transaction data:

1. HETEROGENEOUS ENTITY GRAPH (full context, for visualization/explainability)
   Node types: Merchant, Account, Device, IPSubnet, Instrument
   Edge types: TRANSACTED_AT, USED_DEVICE, ROUTED_THROUGH, PAID_WITH

2. WEIGHTED ACCOUNT CONTACT GRAPH (what SIR actually runs on)
   Nodes: Account only.
   Edge exists between two accounts if they share a device, IP subnet,
   or payment instrument -- i.e. a plausible channel through which
   fraud "risk" could transmit from one account to another.
   Edge weight = an estimated transmission probability, NOT just 1/0 --
   sharing a device is a much stronger signal than sharing a coarse IP
   subnet (could just be the same coffee shop wifi), so weights differ.

   This weighted contact graph is the one thing epidemiology needs and a
   plain fraud classifier doesn't produce: an explicit "how easily does
   compromise spread from A to B" number per edge.
"""

import itertools
from collections import defaultdict
import networkx as nx

# Relative transmission strength per shared attribute type.
# Tune these -- they are the "beta" building blocks for the SIR model.
SHARED_DEVICE_WEIGHT = 0.85      # strongest signal: same physical hardware
SHARED_INSTRUMENT_WEIGHT = 0.65  # same stolen card/VPA being tested
SHARED_IP_WEIGHT = 0.08          # weakest: very often coincidental (shared home/office
                                  # wifi, mobile carrier NAT) -- calibrated deliberately
                                  # low so that ordinary household/office IP-sharing among
                                  # legitimate users does NOT read as an outbreak risk on
                                  # its own. Real fraud rings are identified by STRONGER,
                                  # STACKED signals (shared device and/or instrument),
                                  # not IP alone -- this mirrors how real risk teams treat
                                  # IP overlap as weak corroborating evidence, never a
                                  # standalone trigger.


def build_heterogeneous_graph(df):
    G = nx.Graph()
    for _, row in df.iterrows():
        m, a, d, ip, inst = (
            f"M::{row.merchant}", f"A::{row.account}", f"D::{row.device}",
            f"IP::{row.ip_subnet}", f"I::{row.instrument}",
        )
        G.add_node(m, type="Merchant")
        G.add_node(a, type="Account", label=row.label)
        G.add_node(d, type="Device")
        G.add_node(ip, type="IPSubnet")
        G.add_node(inst, type="Instrument")
        G.add_edge(a, m, type="TRANSACTED_AT")
        G.add_edge(a, d, type="USED_DEVICE")
        G.add_edge(a, ip, type="ROUTED_THROUGH")
        G.add_edge(a, inst, type="PAID_WITH")
    return G


def build_contact_graph(df):
    """
    Collapse the heterogeneous graph into an Account-only weighted graph.
    Any two accounts that share a device/ip/instrument get an edge whose
    weight is the MAX of the relevant shared-attribute weights (if they
    share both a device AND an ip, that's an even stronger signal, but we
    keep it simple with max() rather than summing above 1.0).
    """
    device_to_accounts = defaultdict(set)
    ip_to_accounts = defaultdict(set)
    inst_to_accounts = defaultdict(set)
    account_labels = {}

    for _, row in df.iterrows():
        device_to_accounts[row.device].add(row.account)
        ip_to_accounts[row.ip_subnet].add(row.account)
        inst_to_accounts[row.instrument].add(row.account)
        account_labels[row.account] = row.label

    edge_weight = defaultdict(float)

    def add_pairs(groups, weight):
        for accounts in groups.values():
            if len(accounts) < 2:
                continue
            for a, b in itertools.combinations(sorted(accounts), 2):
                key = (a, b)
                edge_weight[key] = max(edge_weight[key], weight)

    add_pairs(device_to_accounts, SHARED_DEVICE_WEIGHT)
    add_pairs(ip_to_accounts, SHARED_IP_WEIGHT)
    add_pairs(inst_to_accounts, SHARED_INSTRUMENT_WEIGHT)

    C = nx.Graph()
    for acc, label in account_labels.items():
        C.add_node(acc, label=label)
    for (a, b), w in edge_weight.items():
        C.add_edge(a, b, weight=w)

    return C


if __name__ == "__main__":
    import pandas as pd
    df = pd.read_csv("synthetic_transactions.csv")
    hetero = build_heterogeneous_graph(df)
    contact = build_contact_graph(df)
    print(f"Heterogeneous graph: {hetero.number_of_nodes()} nodes, {hetero.number_of_edges()} edges")
    print(f"Contact graph:       {contact.number_of_nodes()} nodes, {contact.number_of_edges()} edges")
    comps = list(nx.connected_components(contact))
    sized = sorted(comps, key=len, reverse=True)[:5]
    print("Largest connected components in contact graph:", [len(c) for c in sized])
