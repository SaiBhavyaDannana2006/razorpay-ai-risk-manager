"""
audit_trail.py
---------------------------------
Every cluster-level risk decision gets written as a structured, queryable
row -- not a black-box score. This is what makes the system defensible
to a compliance/risk team: anyone can pull up exactly which graph metrics
drove a given containment recommendation.
"""

import sqlite3
import json
import datetime

DB_PATH = "audit_trail.db"


def init_db(path: str = DB_PATH):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS risk_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            cluster_size INTEGER,
            r0 REAL,
            outbreak_capable INTEGER,
            dominant_label TEXT,
            recommended_action TEXT,
            quarantine_count INTEGER,
            quarantine_accounts TEXT,
            r0_after_containment REAL,
            estimated_loss_avoided_usd REAL,
            friction_cost_usd REAL,
            net_benefit_usd REAL,
            raw_metrics_json TEXT
        )
    """)
    conn.commit()
    return conn


def log_decision(conn, cluster_info: dict, quarantine_list: list,
                  r0_trace: list, roi: dict):
    action = "CONTAIN" if cluster_info["outbreak_capable"] else "MONITOR"
    conn.execute("""
        INSERT INTO risk_decisions (
            timestamp, cluster_size, r0, outbreak_capable, dominant_label,
            recommended_action, quarantine_count, quarantine_accounts,
            r0_after_containment, estimated_loss_avoided_usd,
            friction_cost_usd, net_benefit_usd, raw_metrics_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.datetime.utcnow().isoformat(),
        cluster_info["size"],
        cluster_info["r0"],
        int(cluster_info["outbreak_capable"]),
        cluster_info["dominant_label"],
        action,
        len(quarantine_list),
        json.dumps(quarantine_list),
        r0_trace[-1] if r0_trace else None,
        roi.get("estimated_loss_avoided_usd") if roi else None,
        roi.get("friction_cost_usd") if roi else None,
        roi.get("net_benefit_usd") if roi else None,
        json.dumps({"r0_trace": r0_trace, "roi": roi}),
    ))
    conn.commit()


def fetch_all(path: str = DB_PATH):
    conn = sqlite3.connect(path)
    cur = conn.execute("SELECT * FROM risk_decisions ORDER BY id DESC")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


if __name__ == "__main__":
    for row in fetch_all():
        print(row)
