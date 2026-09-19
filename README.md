# AI Data Architect

Explainable AI-Powered Data Storage Architecture & Optimization Advisor. Given a workload scenario (users, growth rate, data types, latency/availability requirements, compliance constraints), the system produces a deterministic, fully-traceable storage architecture recommendation with cost/performance impact estimates. A rules engine makes every decision; AWS Bedrock provides optional natural-language explanations and input parsing. Every recommendation traces the full chain: requirement → detected problem → technique → expected effect → trade-off.

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                         Streamlit UI (:8501)                          │
│  Architect │ Recommendation │ Impact │ Real Cost │ Growth Roadmap     │
│  Why? │ Analytics │ What-If                                           │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────────┐
│                      FastAPI REST API (:8000)                          │
│  /scenarios  /recommendations  /explain  /what-if  /pricing           │
│  /real-cost  /trajectory  /export/terraform                           │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────────────┐
│                    Deterministic Rules Engine                           │
│                                                                        │
│  Scenario ─► Profiler ─► Problem Detector ─► Candidate Gen             │
│  ─► Rule Evaluation ─► Constraint Filter ─► Conflict Resolve           │
│  ─► Strategy Construction ─► Impact Estimation ─► Architecture         │
└────────────┬────────────────────────────────┬──────────────────────────┘
             │                                │
┌────────────▼────────────┐  ┌────────────────▼─────────────────────────┐
│  Knowledge Base          │  │  AWS Integrations                       │
│  19 techniques           │  │  Bedrock (NL explain / parse)           │
│  YAML-driven rules       │  │  S3 (result storage)                    │
│  14 problem types        │  │  RDS/SQLite (metadata)                  │
└─────────────────────────┘  │  Pricing API (real cost estimates)       │
                             └──────────────────────────────────────────┘
```

## Features

- **Deterministic Architecture Recommendations** — rules engine evaluates 19 techniques against 14 problem types. No LLM in the decision loop.
- **Full Explainability** — every recommendation traces requirement → problem → technique → effect → trade-off. Bedrock adds natural-language explanations when available; structured fallback always works.
- **Real AWS Cost Estimates** — live pricing from the AWS Pricing API (S3, RDS, ElastiCache, Glacier) with per-component line items and regional comparison.
- **Growth Trajectory Simulator** — 24-month projection of architecture evolution with compound user growth, tipping point detection (priority escalations, new techniques, architecture changes), and monthly cost tracking.
- **Terraform Scaffold Generator** — downloadable `.tf` files (main, variables, outputs) mapped from the recommended architecture. Includes multi-AZ, lifecycle rules, and a zip bundle with `terraform.tfvars.example`.
- **Confidence Bands** — impact estimates augmented with 25th–75th percentile ranges derived from 2,000 synthetic scenarios via DuckDB analytical queries.
- **What-If Analysis** — modify any scenario parameter and see which techniques change priority, get added, or get removed.
- **Analytics Dashboard** — technique frequency charts, co-occurrence network, domain distribution, and ML experiment comparison across the synthetic dataset.

## AWS Services Used

| Service | Purpose | Required? |
|---------|---------|-----------|
| **Amazon Bedrock** (Nova Lite) | Natural-language explanation of recommendations and free-text scenario parsing | No — falls back to structured explanations |
| **Amazon S3** | Persistent storage for scenario results and analytics Parquet files | No — local filesystem fallback |
| **Amazon RDS** (PostgreSQL) | Metadata store for scenario runs, recommendation history, and domain statistics | No — SQLite fallback |
| **AWS Pricing API** | Real-time list prices for S3, RDS, ElastiCache, Glacier cost estimates | No — cached defaults if unreachable |
| **Amazon ElastiCache** | Recommended in architectures for read-heavy workloads (not used by the tool itself) | N/A |

All AWS services degrade gracefully — the core engine is fully functional without any AWS credentials.

## Quick Start

```bash
git clone <repo-url> && cd ai-data-architect
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run the UI (no AWS credentials needed):
```bash
streamlit run app/streamlit_app.py
```

Run with AWS integrations:
```bash
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

## Running the Test Suite

```bash
pytest tests/ -v
```

215 tests covering: Pydantic validation (38), workload profiling (20), problem detection (22), recommendation engine (16), impact estimation (10), architecture builder (7), analytics pipeline (16), API endpoints (8), Streamlit smoke tests (2), Bedrock integration (11), AWS stores (9), what-if analysis (5), ML experiment (4), growth trajectory (9), Terraform export (11), confidence bands (4), real-cost pricing (13).

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
    Storage: 5,000 GB -> 1,140 GB (77% reduction)  [range: 65–84%]
    Cost:    $115/mo -> $13/mo (88% savings)        [range: 72–93%]

  REAL AWS COST (us-east-1):
    S3 Standard:  $11.50/mo
    RDS db.r6g:   $438.00/mo
    ElastiCache:  $109.50/mo
    Total:        $559.00/mo
```

## Pipeline

```
Scenario → Validation → Profiling → Problem Detection → Candidate Generation
    → Rule Evaluation → Conflict Resolution → Strategy Construction
    → Impact Estimation → Architecture Building → Alternatives Generation
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/scenarios` | POST | Validate and normalize a scenario |
| `/api/v1/recommendations` | POST | Full recommendation pipeline |
| `/api/v1/explain` | POST | Bedrock or structured explanation |
| `/api/v1/what-if` | POST | Compare baseline vs. modified scenario |
| `/api/v1/pricing` | GET | Raw AWS list prices by region |
| `/api/v1/real-cost` | POST | Per-component cost estimate |
| `/api/v1/trajectory` | POST | Growth trajectory simulation |
| `/api/v1/export/terraform` | POST | Generate Terraform scaffold |
| `/health` | GET | Engine health and version info |

## Regenerating Synthetic Data

```bash
python -c "from storage_advisor.analytics.generator import ScenarioGenerator; ScenarioGenerator().generate()"
```

Produces `data/synthetic/scenarios.parquet` (2,000 rows, 47 columns) and `data/synthetic/scenarios.csv`. The generator uses 8 domain-specific probability priors to create realistic workload distributions.

## Synthetic Data Disclaimer

All data in `data/synthetic/` is generated programmatically using probability distributions calibrated to approximate realistic storage workloads. It does not contain real customer data, production metrics, or proprietary information. The analytics charts, ML experiment results, and benchmark comparisons derived from this data are illustrative of system capabilities and should not be interpreted as measured production outcomes or guaranteed performance claims.

## Known Limitations

- **Impact estimates are model-based projections**, not measured benchmarks. Actual savings depend on data distribution, access patterns, and implementation quality. All estimates are labeled explicitly.
- **Confidence bands are derived from synthetic data.** The 25th–75th percentile ranges reflect variance across generated scenarios, not production measurements.
- **Single-region architecture only.** The engine does not yet model multi-region replication, cross-region latency, or data residency requirements beyond compliance flags.
- **Terraform scaffolds are starting points.** Generated `.tf` files require VPC, subnet, and security group configuration before `terraform apply`.
- **No feedback loop.** Recommendations are one-shot — the system does not yet ingest production telemetry to validate or refine its estimates over time.
- **Growth trajectory assumes compound user growth and linear storage scaling.** Real growth patterns may be non-linear or seasonal.

## Documentation

- [Domain Model](docs/domain_model.md) — scenario fields, enums, validation rules
- [Recommendation Logic](docs/recommendation_logic.md) — pipeline stages, scoring, conflict resolution
- [Assumptions](docs/assumptions.md) — every impact estimation assumption with rationale
- [Demo Script](docs/demo_script.md) — 8-minute walkthrough for live demos

## Tech Stack

- Python 3.11+ / Pydantic v2 / FastAPI / Streamlit / Plotly
- AWS Bedrock (Nova Lite) / S3 / RDS (PostgreSQL) / Pricing API / SQLAlchemy
- DuckDB (analytics) / NumPy (confidence bands) / scikit-learn (ML experiment) / NetworkX (co-occurrence)
- Jinja2 (Terraform templates) / Docker / docker-compose for deployment
