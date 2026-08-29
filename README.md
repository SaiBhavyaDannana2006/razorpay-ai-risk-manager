# Outbreak Control Room

Razorpay AI Buildathon — Track 02: AI Risk Manager

## Overview

Outbreak Control Room is a fraud-forecasting and intervention-planning dashboard built to model cross-merchant fraud rings as epidemiological outbreaks. Just as public health teams track how diseases spread across a contact network, this project models stolen-card testing, mule account rings, and suspicious merchant-to-merchant propagation as an SIR-style infection process over a graph of shared devices, IP subnets, instruments, and merchant relationships.

The system answers a more actionable question than "Is this transaction fraud?":

- How far could a compromised account ring spread if left unchecked?
- Which accounts are most critical to quarantine?
- What is the minimum containment set that reduces transmission below a self-limiting threshold?
- What is the net benefit of intervention when compared against fraud loss and customer friction?

Modern fraud rings are adversarial and distributed. A single merchant rarely sees enough bad activity to identify a networked syndicate, but the combined signal across merchants reveals the outbreak. Outbreak Control Room treats fraud rings as an epidemic on a graph, enabling risk operators to detect hidden propagation patterns before losses become systemic.

## Key features

- Dynamic SIR-inspired outbreak simulation across merchant-linked account graphs
- Interactive graph view of outbreak propagation, with cluster filtering
- Timeline scrubber showing transitions from Susceptible to Infected to Contained states
- Real-time odometer-style counters tracking cases at each step
- Threat signal summary metrics including R0, outbreak classification, and response counts
- ROI calculator and scenario controls for average fraud loss and customer interruption cost
- Audit-ready analysis of cluster severity, quarantine sets, and net benefit

## Architecture

The project combines a graph representation of risk activity with an epidemiological spread model:

- Synthetic transaction seeds provide realistic merchant, device, IP, and instrument behavior
- A heterogeneous account graph is constructed from shared signals across merchants
- Community detection identifies suspicious subgraphs
- SIR-style simulation estimates cluster reproduction number (R0)
- Containment analysis prioritizes bridge accounts and calculates ROI
- Streamlit dashboard surfaces the risk state to decision-makers in real time

### Production-readiness note

For a production Razorpay deployment, the same graph computation can be run as a scheduled batch pipeline over streaming payment activity. A typical architecture would include:

- Kafka for ingesting transaction events and account interaction streams
- A graph database or property graph store for persistent relationship modeling
- A batch graph processing layer that periodically updates cluster risk and outbreak summaries
- Real-time serving APIs that return the latest account, cluster, and audit state to downstream risk systems

This design keeps expensive graph analytics out of the per-transaction hot path while still enabling near-real-time operational visibility.

## Project structure

```text
.
├── app.py                    # Streamlit outbreak control room dashboard
├── api.py                   # API serving layer for cluster and account summaries
├── audit_trail.py           # Audit logging utilities
├── calibrate.py             # Tuned edge-weight and GAMMA validation script
├── containment.py          # Quarantine logic and ROI calculations
├── generate_synthetic_data.py
├── graph_builder.py        # Graph construction from transaction data
├── main_demo.py            # End-to-end pipeline runner
├── requirements.txt        # Python dependencies
├── sir_model.py            # SIR simulation and R0 logic
├── README.md               # Project documentation
├── .gitignore              # Git exclusions
└── demo_outputs/           # Generated reports, plots, and JSON snapshots
```

## Local setup

### 1) Clone the repository

```bash
git clone <your-github-repo-url>
cd <repo-folder>
```

### 2) Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Generate the synthetic dataset

```bash
python generate_synthetic_data.py
```

### 5) Run the end-to-end pipeline

```bash
python main_demo.py
```

### 6) Launch the dashboard

```bash
streamlit run app.py
```

Then open the local URL displayed in the terminal (typically http://localhost:8501).

## Optional API usage

The project also includes a lightweight FastAPI layer for serving risk endpoints:

```bash
uvicorn api:app --reload --port 8000
```

Example requests:

```bash
curl http://localhost:8000/clusters
curl http://localhost:8000/risk/<account_hash>
curl http://localhost:8000/audit
```

## Expected outcome

The project identifies suspicious multi-merchant clusters that behave like real outbreak vectors, while correctly distinguishing them from ordinary coincidental overlap. In the default synthetic dataset it detects three outbreak-capable ring clusters, each with substantial positive ROI for targeted containment.

## Demo summary

- 424 synthetic transactions across 12 merchants
- 136 multi-account clusters scanned
- 3 outbreak-capable clusters detected
- All flagged clusters have strong containment ROI under the modeled loss assumptions
- Network propagation and risk state are visible in the interactive dashboard

## License

This project is developed for the Razorpay AI Buildathon and intended for demonstration and research-oriented analysis.
