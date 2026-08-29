"""
api.py
---------------------------------
Lean FastAPI serving layer. On startup it loads the precomputed graph +
cluster report (built by main_demo.py) so requests are fast lookups, not
full re-simulations -- exactly how you'd want this to behave in
production: heavy graph/SIR computation runs as a periodic batch job,
the API just serves the latest computed risk state per account.

Run with:
    uvicorn api:app --reload --port 8000

Then try:
    GET /risk/{account_hash}
    GET /clusters
    GET /audit
"""

import json
import pandas as pd
from fastapi import FastAPI, HTTPException

from graph_builder import build_contact_graph
from sir_model import cluster_report
from containment import find_min_containment_set, estimate_intervention_roi
import audit_trail

app = FastAPI(title="Outbreak Guard - Fraud Epidemic Risk API")

# ---- Load + precompute once at startup (batch-style, not per-request) ----
_df = pd.read_csv("synthetic_transactions.csv")
_C = build_contact_graph(_df)
_clusters = cluster_report(_C)

_account_to_cluster = {}
_cluster_results = []

_conn = audit_trail.init_db()

for c in _clusters:
    entry = {"cluster": c, "quarantine": [], "r0_trace": [c["r0"]], "roi": None}
    if c["outbreak_capable"]:
        q_list, r0_trace = find_min_containment_set(_C, c["cluster_nodes"])
        roi = estimate_intervention_roi(_C, c["cluster_nodes"], q_list)
        entry.update({"quarantine": q_list, "r0_trace": r0_trace, "roi": roi})
        audit_trail.log_decision(_conn, c, q_list, r0_trace, roi)
    else:
        audit_trail.log_decision(_conn, c, [], [c["r0"]], {})
    _cluster_results.append(entry)
    for node in c["cluster_nodes"]:
        _account_to_cluster[node] = entry


@app.get("/")
def root():
    return {
        "service": "Outbreak Guard",
        "description": "Epidemic-style fraud/mule ring spread forecasting across merchants",
        "endpoints": ["/risk/{account_hash}", "/clusters", "/audit"],
    }


@app.get("/risk/{account_hash}")
def get_risk(account_hash: str):
    entry = _account_to_cluster.get(account_hash)
    if entry is None:
        return {
            "account": account_hash,
            "risk_level": "Low",
            "reason": "Not part of any detected multi-account cluster",
            "recommended_action": "Monitor",
        }
    c = entry["cluster"]
    risk_level = "High" if c["outbreak_capable"] else "Medium"
    action = "Contain (block/step-up-verify quarantine set)" if c["outbreak_capable"] else "Monitor"
    return {
        "account": account_hash,
        "risk_level": risk_level,
        "cluster_size": c["size"],
        "cluster_r0": c["r0"],
        "outbreak_capable": c["outbreak_capable"],
        "in_recommended_quarantine_set": account_hash in entry["quarantine"],
        "recommended_action": action,
        "audit_metric": f"CLUSTER_R0={c['r0']}, SIZE={c['size']}, DOMINANT_LABEL={c['dominant_label']}",
    }


@app.get("/clusters")
def get_clusters():
    out = []
    for entry in _cluster_results:
        c = entry["cluster"]
        out.append({
            "size": c["size"],
            "r0": c["r0"],
            "outbreak_capable": c["outbreak_capable"],
            "dominant_label": c["dominant_label"],
            "quarantine_count": len(entry["quarantine"]),
            "r0_after_containment": entry["r0_trace"][-1] if entry["r0_trace"] else None,
            "roi": entry["roi"],
        })
    return out


@app.get("/audit")
def get_audit():
    return audit_trail.fetch_all()
