"""
generate_synthetic_data.py
---------------------------------
Builds a synthetic multi-merchant transaction dataset since real Razorpay
data isn't available for a hackathon. The goal is NOT to be a realistic
fraud simulator -- it's to produce a graph with the exact structural
properties we need to demo epidemic-style spread:

  1. Several "syndicate clusters": groups of accounts that share a device
     and/or IP subnet across DIFFERENT merchants (this is the pattern a
     single merchant can never see on their own).
  2. Some "isolated fraud": a lone bad account with no shared
     infrastructure -- included on purpose as a contrast case, to prove
     the model correctly does NOT predict epidemic spread for fraud that
     isn't actually a ring.
  3. A large pool of ordinary, unconnected legitimate accounts (noise).

Every identifier that would be PII in a real system (device id, IP,
account id, payment instrument) is hashed before it's used anywhere else
in the pipeline. In a real deployment this hashing would happen at the
merchant/edge layer before anything reaches a shared graph -- here we do
it immediately after generation to keep the same guarantee.
"""

import hashlib
import random
import pandas as pd

random.seed(42)

N_MERCHANTS = 12
N_LEGIT_ACCOUNTS = 400
N_SYNDICATE_CLUSTERS = 3
SYNDICATE_CLUSTER_SIZE_RANGE = (6, 14)   # accounts per ring
N_ISOLATED_FRAUD = 5                     # lone bad actors, no shared infra


def h(value: str) -> str:
    """Privacy-preserving hash -- stand-in for HMAC-SHA256 w/ rotating salt."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def make_merchants():
    return [h(f"merchant_{i}") for i in range(N_MERCHANTS)]


def make_legit_transactions(merchants):
    rows = []
    for i in range(N_LEGIT_ACCOUNTS):
        acc = h(f"user_{i}")
        device = h(f"device_{i}")          # unique device per legit user
        ip_subnet = h(f"ip_{i // 3}")       # loose sharing, e.g. same household/office
        instrument = h(f"card_{i}")
        merchant = random.choice(merchants)
        rows.append({
            "merchant": merchant, "account": acc, "device": device,
            "ip_subnet": ip_subnet, "instrument": instrument,
            "label": "legit",
        })
    return rows


def make_syndicate_clusters(merchants):
    """
    Each cluster = a set of accounts that ALL share one device and/or one
    IP subnet, but transact across DIFFERENT merchants. This is exactly
    the pattern that's invisible to any single merchant and only shows up
    once you look at the graph across tenants.
    """
    rows = []
    for c in range(N_SYNDICATE_CLUSTERS):
        size = random.randint(*SYNDICATE_CLUSTER_SIZE_RANGE)
        shared_device = h(f"ring_device_{c}")
        shared_ip = h(f"ring_ip_{c}")
        shared_instrument = h(f"ring_card_{c}")  # some rings also test one stolen card
        cluster_merchants = random.sample(merchants, k=min(len(merchants), size))
        for j in range(size):
            acc = h(f"ring{c}_user_{j}")
            # mix of shared-device-only, shared-ip-only, and shared-both accounts
            device = shared_device if random.random() < 0.7 else h(f"ring{c}_device_{j}")
            ip_subnet = shared_ip if random.random() < 0.6 else h(f"ring{c}_ip_{j}")
            instrument = shared_instrument if random.random() < 0.3 else h(f"ring{c}_card_{j}")
            merchant = cluster_merchants[j % len(cluster_merchants)]
            rows.append({
                "merchant": merchant, "account": acc, "device": device,
                "ip_subnet": ip_subnet, "instrument": instrument,
                "label": f"syndicate_{c}",
            })
    return rows


def make_isolated_fraud(merchants):
    """Lone bad actors with NO shared infrastructure -- should NOT trigger
    epidemic spread, only a local risk flag. This is the contrast case."""
    rows = []
    for i in range(N_ISOLATED_FRAUD):
        acc = h(f"lone_fraud_{i}")
        rows.append({
            "merchant": random.choice(merchants),
            "account": acc,
            "device": h(f"lone_device_{i}"),
            "ip_subnet": h(f"lone_ip_{i}"),
            "instrument": h(f"lone_card_{i}"),
            "label": "isolated_fraud",
        })
    return rows


def build_dataset() -> pd.DataFrame:
    merchants = make_merchants()
    rows = (
        make_legit_transactions(merchants)
        + make_syndicate_clusters(merchants)
        + make_isolated_fraud(merchants)
    )
    df = pd.DataFrame(rows)
    return df.sample(frac=1, random_state=42).reset_index(drop=True)


if __name__ == "__main__":
    df = build_dataset()
    df.to_csv("synthetic_transactions.csv", index=False)
    print(f"Generated {len(df)} rows -> synthetic_transactions.csv")
    print(df["label"].value_counts())
