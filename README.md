# AI Data Architect

Enterprise cloud storage intelligence platform — Explainable by design.

---

## Overview

AI Data Architect is an automated infrastructure advisory platform for distributed systems engineering. Given a high-dimensional workload specification—ingestion velocity, concurrency, structured versus unstructured data ratios, latency budgets, availability targets, and regulatory compliance constraints—the platform synthesizes a production-grade AWS storage architecture accompanied by quantitative cost, storage, and performance projections.

Unlike black-box generative systems, AI Data Architect decouples architectural authority from narrative generation. Every decision is computed deterministically by an auditable rule engine, enforcing full traceability from requirement to detected problem, recommended technique, expected impact, and operational trade-off.

---

## Quickstart

### Option A: Docker Compose (Recommended)

1. Clone the repository and configure the environment:
```bash
git clone https://github.com/simply-mihir/ai-storage.git
cd ai-storage
cp .env.example .env
```

2. Start the containerized services:
```bash
docker compose up --build
```

The application is accessible at `http://localhost:8001`. The API documentation is available at `http://localhost:8001/docs`.

### Option B: Local Python Development

1. Create and activate a Python 3.11+ virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,prod]"
```

2. Run the application service:
```bash
uvicorn storage_advisor.app.api:app --host 0.0.0.0 --port 8001
```

### Environment Configuration

The application degrades gracefully: all core recommendation, profiling, impact modeling, and analytical store capabilities function entirely offline with zero cloud credentials.

| Variable | Type | Default | Description |
|---|---|---|---|
| `API_KEYS` | String (CSV) | `dev-demo-key` | Comma-separated list of valid API keys for authenticating against `/api/v1/*` routes. |
| `ENV` | String | `dev` | Deployment environment mode (`dev`, `staging`, `prod`). When set to `dev`, unauthenticated requests fall back to `dev-demo-key`. In `prod`, missing keys return `401 Unauthorized`. |
| `AWS_REGION` | String | `us-east-1` | AWS region targeted for live pricing and cloud integrations. |
| `AWS_ACCESS_KEY_ID` | String | None | Optional credentials for cloud AI inference and storage services. |
| `AWS_SECRET_ACCESS_KEY` | String | None | Optional credentials for cloud AI inference and storage services. |
| `LLM_FALLBACK_KEY` | String | None | Optional API key for secondary LLM explanation fallback tier. |
| `S3_BUCKET_NAME` | String | None | Optional S3 bucket for cloud storage integration. |
| `DATABASE_URL` | String | None | PostgreSQL connection URI for the system-of-record store. Omit for graceful offline degradation. |
| `LLM_MODEL_ID` | String | `amazon.nova-lite-v1:0` | Model identifier for the primary cloud LLM inference tier. |
| `PORT` | Integer | `8001` | TCP port binding for the FastAPI web server. |

---

## API Endpoint Reference

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/v1/config` | Client configuration (env, API key mode) |
| `POST` | `/api/v1/scenarios` | Create a workload scenario and run the detection pipeline |
| `POST` | `/api/v1/recommendations` | Generate prioritized technique recommendations |
| `POST` | `/api/v1/explain` | Produce AI-synthesized architectural rationale |
| `POST` | `/api/v1/what-if` | Compare two scenario variants side by side |
| `POST` | `/api/v1/second-opinion` | ML second-opinion advisory verdict |
| `GET` | `/api/v1/pricing` | Live AWS list-rate pricing parameters |
| `POST` | `/api/v1/real-cost` | Itemized monthly cost projection with line items |
| `POST` | `/api/v1/trajectory` | 24-month growth and cost trajectory simulation |
| `POST` | `/api/v1/export/terraform` | Generate production Terraform (HCL) scaffold |
| `POST` | `/api/v1/report` | Build consultant-grade report payload |
| `GET` | `/api/v1/report/export` | Export report as Markdown or PDF (`?format=md\|pdf`) |
| `GET` | `/api/v1/insights` | Analytics figures (Plotly JSON specs) |
| `GET` | `/health` | Liveness probe (open, no auth required) |
| `GET` | `/metrics` | Prometheus metrics export |

---

## Feature Tour: Platform Tabs

The single-page dashboard organizes complex architectural analysis into eight coordinated views:

1. **Tab 1: Architect (Workload Configuration)**
   - Interactive specification of company size, user scale, daily ingestion velocity, data type distribution, and read/write intensity.
   - Pydantic v2 validation ensuring schema consistency with real-time feedback.
   - Pre-configured enterprise templates (E-Commerce, Generative AI, Financial Audit, Telemetry).

2. **Tab 2: Recommendations (Deterministic Core & Advisory ML)**
   - Priority-ranked technique recommendations (`REQUIRED`, `RECOMMENDED`, `OPTIONAL`, `AVOID`).
   - Explicit decision trace: requirement -> detected problem -> technique -> impact -> trade-off.
   - **ML Second-Opinion Card**: Integrated ClassifierChain distillation model providing an independent advisory verdict. Displays agreement percentages and highlights divergence features for human engineering review.

3. **Tab 3: Impact (Quantitative Projections)**
   - Model-based projections of storage volume reduction (GB and percentage), monthly cost savings (USD), and latency improvements.
   - Percentile confidence bands (P25 to P75) derived from DuckDB historical analytical models.
   - Transparent simulation assumptions panel documenting regression weights and transition parameters.

4. **Tab 4: Real Cost (AWS List-Verified Pricing)**
   - Itemized monthly architectural bill covering S3 Standard storage, S3 Data Transfer Out (regional internet egress), S3 API request tiers (PUT/POST at $0.005/1k, GET at $0.0004/1k), RDS PostgreSQL instances, RDS gp3 baseline storage (including 3,000 IOPS and 125 MB/s at zero extra cost), and ElastiCache Redis nodes.
   - Dual-currency formatting with live USD to INR conversion.
   - Spend distribution doughnut chart visualizing cost center proportions across storage, compute, and networking.

5. **Tab 5: Explainability (Rationale Synthesis & Audit Chain)**
   - Context-aware architectural rationale synthesis powered by a three-tier resilient fallback chain (cloud LLM tier 1 -> cloud LLM tier 2 -> deterministic structured engine).
   - Chronological decision traceability chain cross-referencing formal knowledge base definitions.

6. **Tab 6: Growth (24-Month Trajectory Simulator)**
   - Continuous simulation of compound user growth and storage accumulation over a 24-month horizon.
   - Automatic detection of critical architectural tipping points triggering priority escalations and new infrastructure requirements.
   - Export of production-ready, modular Terraform (HCL) infrastructure scaffolds.

7. **Tab 7: What-If (Comparative Architecture Diffing)**
   - Side-by-side scenario variant comparison.
   - Delta analysis highlighting added techniques, dropped techniques, priority shifts, and cost/latency deviations.

8. **Tab 8: Insights (Analytics Store & Exploratory Data Analysis)**
   - Embedded DuckDB analytics engine querying 2,000 historical scenario benchmarks.
   - Interactive visualizations: technique frequency histograms, correlation heatmaps, co-occurrence network graphs, and multi-dimensional bubble plots.

---

## Architecture Summary

The platform operates on a six-stage deterministic data pipeline:

```
Scenario -> Profiling -> Problem Detection -> Recommendation Engine -> Impact Estimation -> Architecture Building -> Report Generation
```

### Architectural Decisions

- **Deterministic Engine Authority**: The recommendation engine is 100% deterministic and auditable. Generative models operate strictly as downstream explanation synthesizers.
- **Dual-Track API Exposure**: Full backward compatibility across schema v1 and v2 with transparent ingress normalization.
- **OLTP vs. OLAP Separation**: Relational transactional metadata is decoupled from embedded DuckDB columnar analytics over partitioned Parquet datasets.
- **ML Second-Opinion Governance**: Machine learning models serve strictly in an advisory capacity and never override engine authority.

For complete architectural specifications, sequence diagrams, and design registers, refer to [ARCHITECTURE.md](file:///Users/mihir/Desktop/ai-storage/ARCHITECTURE.md).

---

## Validation Summary

- **Synthetic Self-Consistency Benchmark**: The engine was validated across a curated corpus of 2,000 multi-dimensional workload scenarios (`data/synthetic/scenarios.parquet`). Under holdout evaluation, the distillation model achieved a mean Jaccard self-consistency score exceeding 0.80, demonstrating predictable and uniform rule enforcement across diverse workload configurations.
- **Empirical Literature Validation**: Real-world validation was conducted by encoding public production workloads from Netflix (media streaming) and Uber (event-sourced mobility). The engine achieved 100.0% alignment against documented production infrastructure choices (14 of 14 techniques verified against published technical literature).

For detailed comparative alignment tables, citation links, and mismatch analyses, refer to [CASE_STUDY.md](file:///Users/mihir/Desktop/ai-storage/CASE_STUDY.md).

---

## Test Suite & Verification

The repository maintains an automated testing suite covering algorithmic correctness, rate limiting, Prometheus metrics, pricing integrations, and CLI utilities:

```bash
# Run complete test suite
pytest -q

# Run static linting
ruff check .

# Execute case study alignment benchmark CLI
python scripts/case_study.py --workload all
```

All 467 tests execute in under 60 seconds on standard local environments.

---

## Upgrading

The following environment variable names were renamed. The old names still work for one release and emit a `DeprecationWarning` at startup:

| Old Name | New Name |
|---|---|
| `BEDROCK_MODEL_ID` | `LLM_MODEL_ID` |
| `GROQ_API_KEY` | `LLM_FALLBACK_KEY` |

Update your `.env` and deployment configs before the next major release.

---

## Roadmap

- [ ] **Multi-Region Active-Active Topology Modeling**: Automated cross-region replication latency and ingress/egress cost modeling.
- [ ] **Telemetry Ingestion Loop**: Direct CloudWatch and Prometheus metric ingestion to evaluate live production architectures against baseline recommendations.
- [ ] **Kubernetes Operator & CSI Driver Policies**: Generation of dynamic storage class configurations, volume snapshot rules, and CSI driver parameters.
- [ ] **Carbon & Sustainability Metrics**: Estimation of operational carbon footprint (gCO2e/GB-month) based on AWS regional renewable energy ratings.

---

## License

This project is licensed under the Apache License, Version 2.0. See the `LICENSE` file for details.
