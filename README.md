# AI Data Architect

Explainable AI-Powered Data Storage Architecture & Optimization Advisor. Given a workload scenario (users, growth rate, data types, latency/availability requirements, compliance constraints), the system produces a deterministic, fully-traceable storage architecture recommendation with cost/performance impact estimates. A rules engine makes every decision; AWS Bedrock provides optional natural-language explanations and input parsing. Every recommendation traces the full chain: requirement → detected problem → technique → expected effect → trade-off.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      Streamlit UI (:8501)                      │
│  Architect │ Recommendation │ Impact │ Why? │ Analytics │WhatIf│
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│                    FastAPI REST API (:8000)                     │
│  /api/v1/scenarios  /recommendations  /explain  /what-if       │
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│                  Deterministic Rules Engine                     │
│                                                                │
│  Scenario ─► Profiler ─► Problem Detector ─► Candidate Gen     │
│  ─► Rule Evaluation ─► Constraint Filter ─► Conflict Resolve   │
│  ─► Strategy Construction ─► Impact Estimation ─► Architecture │
└──────────┬──────────────────────────┬──────────────────────────┘
           │                          │
┌──────────▼──────────┐  ┌───────────▼───────────────────────┐
│  Knowledge Base      │  │  AWS Integrations                 │
│  19 techniques       │  │  Bedrock (NL explain / parse)     │
│  YAML-driven rules   │  │  S3 (result storage)              │
│  14 problem types    │  │  RDS/SQLite (metadata)            │
└─────────────────────┘  └───────────────────────────────────┘
```

## Quick Start

```bash
git clone <repo-url> && cd ai-data-architect
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in your AWS credentials
python scripts/aws_setup.py
streamlit run app/streamlit_app.py
```

The app runs at `http://localhost:8501`. The FastAPI docs are at `http://localhost:8000/docs` when started separately with `uvicorn storage_advisor.app.api:app`.

## Docker Setup

```bash
cp .env.example .env   # fill in credentials
docker-compose up
```

Streamlit on `:8501`, API on `:8000`. No AWS credentials required for local-only mode — Bedrock falls back to structured explanations and S3/RDS fall back to local SQLite.

## AWS Services Used

| Service | Purpose |
|---------|---------|
| **Amazon Bedrock** (Nova Lite) | Natural-language explanation of recommendations and free-text scenario parsing |
| **Amazon S3** | Persistent storage for scenario results and analytics Parquet files |
| **Amazon RDS** (PostgreSQL) | Metadata store for scenario runs, recommendation history, and domain statistics |
| **Amazon ElastiCache** | Recommended in architectures for read-heavy, low-latency workloads (not used by the tool itself) |

All AWS services degrade gracefully — the core engine is fully functional without any AWS credentials.

## Running the Test Suite

```bash
pytest tests/ -v
```

180 tests covering: Pydantic validation (38), workload profiling (20), problem detection (22), recommendation engine (16), impact estimation (10), architecture builder (7), analytics pipeline (16), API endpoints (5), Streamlit smoke tests (2), Bedrock integration (11), AWS stores (9), what-if analysis (5), ML experiment (4).

## Sample Output

```
SCENARIO: E-Commerce Platform (10M users, 300 GB/day)

  DETECTED PROBLEMS (9):
    [CRITICAL] HIGH_AVAILABILITY_REQUIREMENT
    [HIGH    ] HIGH_STORAGE_GROWTH
    [HIGH    ] HIGH_READ_LATENCY

  ARCHITECTURE COMPONENTS:
    [REQUIRED   ] Amazon S3                   (object storage)
    [REQUIRED   ] Amazon RDS for PostgreSQL   (transactional)
    [REQUIRED   ] Amazon ElastiCache (Redis)  (cache layer)
    [RECOMMENDED] Amazon Redshift             (analytics)
    [RECOMMENDED] Amazon S3 Glacier           (archive tier)

  IMPACT ESTIMATES [MODEL-BASED]:
    Storage: 5,000 GB -> 1,140 GB (77% reduction)
    Cost:    $115/mo -> $13/mo (88% savings)
```

## Regenerating Synthetic Data

```bash
python -c "from storage_advisor.analytics.generator import ScenarioGenerator; ScenarioGenerator().generate()"
```

Produces `data/synthetic/scenarios.parquet` (2,000 rows, 47 columns) and `data/synthetic/scenarios.csv`. The generator uses 8 domain-specific probability priors to create realistic workload distributions.

## Synthetic Data Disclaimer

All data in `data/synthetic/` is generated programmatically using probability distributions calibrated to approximate realistic storage workloads. It does not contain real customer data, production metrics, or proprietary information. The analytics charts, ML experiment results, and benchmark comparisons derived from this data are illustrative of system capabilities and should not be interpreted as measured production outcomes or guaranteed performance claims.

## Known Limitations

- **Impact estimates are model-based projections**, not measured benchmarks. Actual savings depend on data distribution, access patterns, and implementation quality. All estimates are labeled explicitly.
- **Single-region architecture only.** The engine does not yet model multi-region replication, cross-region latency, or data residency requirements beyond compliance flags.
- **No feedback loop.** Recommendations are one-shot — the system does not yet ingest production telemetry to validate or refine its estimates over time.

## Documentation

- [Domain Model](docs/domain_model.md) — scenario fields, enums, validation rules
- [Recommendation Logic](docs/recommendation_logic.md) — pipeline stages, scoring, conflict resolution
- [Assumptions](docs/assumptions.md) — every impact estimation assumption with rationale
- [Demo Script](docs/demo_script.md) — 5-minute walkthrough for live demos

## Pipeline

```
Scenario → Validation → Profiling → Problem Detection → Candidate Generation
    → Rule Evaluation → Conflict Resolution → Strategy Construction
    → Impact Estimation → Architecture Building → Alternatives Generation
```

## Tech Stack

- Python 3.11+ / Pydantic v2 / FastAPI / Streamlit / Plotly
- AWS Bedrock (Nova Lite) / S3 / RDS (PostgreSQL) / SQLAlchemy
- DuckDB (analytics) / scikit-learn (ML experiment) / NetworkX (co-occurrence)
- Docker / docker-compose for deployment
