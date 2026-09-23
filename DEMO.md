# Five-Minute Technical Demonstration Script

A structured, timed walkthrough of the AI Data Architect platform for systems architects, engineering leadership, and platform evaluation panels.

---

## Demonstration Setup

1. **Start Services**:
   ```bash
   docker compose up -d
   ```
   Or locally:
   ```bash
   uvicorn storage_advisor.app.api:app --host 0.0.0.0 --port 8001
   ```
2. **Access Dashboard**: Open `http://localhost:8001` in a modern browser.
3. **Verify Baseline State**: Ensure the application loads with the default Enterprise Multi-Tier scenario (10M expected users, 300 GB/day growth, mixed access pattern, 100 ms latency SLA, SOC2 compliance).

---

## Timing & Talking Points

### 0:00 - 0:45 | Tab 1: Architect (Workload Specification & Invariants)

* **Action**: Review the input panel parameters. Select the "Enterprise E-Commerce" template or adjust current storage to 25,000 GB with 300 GB daily growth.
* **Key Talking Points**:
  - "Distributed storage decisions are frequently made too late—after data sprawl, performance degradation, and unexpected cloud bills have already set in."
  - "AI Data Architect begins with a formal, strictly-typed workload specification. Using Pydantic v2, every input is validated at ingress against domain boundary constraints."
  - "The system calculates derived workload invariants: daily byte ingestion velocity, read versus write IOPS ratios, and working-set retention horizons."

---

### 0:45 - 1:30 | Tab 2: Recommendations (Deterministic Core & ML Second-Opinion)

* **Action**: Click "Generate Architecture". Observe the ranked technique list and the ML Second-Opinion card.
* **Key Talking Points**:
  - "Notice the immediate priority stratification: `REQUIRED`, `RECOMMENDED`, and `OPTIONAL`. Techniques like Object Storage, Replication, and Sharding are marked `REQUIRED` because specific hard constraints—high growth and availability targets—triggered them."
  - "Every recommendation provides a complete, auditable trace: requirement -> detected problem -> technique -> expected impact -> trade-off."
  - "Highlight the **ML Second-Opinion Card**: We have trained a logistic ClassifierChain model over 2,000 scenario-recommendation pairs. The governance model is strict: the deterministic rules engine is the sole AUTHORITY; the ML model serves purely in an advisory capacity."
  - "The card displays an agreement percentage (typically 80% to 95%). Where the ML model diverged, it highlights the top driving workload features for human engineering review, rather than silently overriding proven rules."

---

### 1:30 - 2:00 | Tab 3: Impact (Quantitative Projections & Confidence Bands)

* **Action**: Switch to the "Impact" tab. Review the three metric cards and the percentile confidence range.
* **Key Talking Points**:
  - "The platform projects quantitative impact: storage volume reduction in gigabytes and percentage, monthly dollar savings, and p99 query latency improvements."
  - "Notice the explicit label: `MODEL-BASED ESTIMATE`. We never present fabricated benchmark numbers. Every estimate is derived from deterministic regression weights calibrated against empirical cloud telemetry."
  - "Below the point estimates, the confidence bands display the 25th to 75th percentile ranges computed via embedded DuckDB queries across similar workload profiles in our 2,000-scenario store."

---

### 2:00 - 2:45 | Tab 4: Real Cost (AWS List-Verified Pricing)

* **Action**: Switch to the "Real Cost" tab. Review the itemized cost table and spend distribution doughnut. Switch the region dropdown from `us-east-1` to `ap-south-1`.
* **Key Talking Points**:
  - "Unlike abstract cost models, this bill is grounded in real AWS public list prices."
  - "Look at the itemization completeness:
    1. S3 Standard storage is separated from cold S3 Glacier Deep Archive storage.
    2. S3 Data Transfer Out (regional internet egress) is calculated explicitly using regional rate tables ($0.09/GB in us-east-1).
    3. S3 API Request Pricing accounts for PUT/POST ($0.005/1k) and GET ($0.0004/1k) operational costs.
    4. RDS PostgreSQL PostgreSQL instances are coupled with RDS gp3 baseline storage, explicitly incorporating the baseline 3,000 IOPS and 125 MB/s included at zero extra cost.
    5. In-memory caching reflects 730 monthly hours of ElastiCache Redis nodes."
  - "The doughnut chart visualizes the true cost center distribution, highlighting network egress and relational IOPS baseline overhead."

---

### 2:45 - 3:15 | Tab 5: Explainability (Rationale Synthesis & Decision Rail)

* **Action**: Switch to the "Explainability" tab. Point to the architectural rationale narrative and scroll through the decision traceability chain.
* **Key Talking Points**:
  - "The platform provides natural-language narrative synthesis without delegating architectural decisions to a black box. The explanation explains what the deterministic engine decided and why."
  - "The decision chain below provides visual verification from requirement to resolution, cross-referencing formal technique definitions from the Knowledge Base v2 catalog."

---

### 3:15 - 3:45 | Tab 6: Growth (24-Month Trajectory & Terraform Export)

* **Action**: Switch to the "Growth" tab. Review the 24-month trajectory line chart and the tipping point markers. Click "Download Terraform Scaffold".
* **Key Talking Points**:
  - "Workloads are not static. The Growth Trajectory Simulator projects compound user growth and storage accumulation across a two-year horizon."
  - "The engine alerts architects to critical tipping points—for instance, month 8 where partitioning escalates from `RECOMMENDED` to `REQUIRED` due to threshold crossings."
  - "With one click, the platform generates a modular Terraform HCL scaffold (`main.tf`, `variables.tf`, `outputs.tf`) ready to initialize the recommended infrastructure."

---

### 3:45 - 4:10 | Tab 7: What-If (Comparative Architecture Diffing)

* **Action**: Switch to the "What-If" tab. Adjust the scenario daily growth parameter from 300 GB to 1,500 GB and click "Compare".
* **Key Talking Points**:
  - "What-If analysis eliminates guesswork during architectural review meetings."
  - "The diff engine highlights exactly which techniques were added, which changed priority bands, and the net deviation in monthly storage and cost."

---

### 4:10 - 4:30 | Tab 8: Insights (Analytics Store & Exploratory Data Analysis)

* **Action**: Switch to the "Insights" tab. Scroll past the technique frequency histogram and co-occurrence network graph.
* **Key Talking Points**:
  - "Tab 8 exposes our embedded DuckDB analytical engine operating directly over 2,000 schema-v2 scenario records stored in columnar Parquet format."
  - "Architects can explore statistical correlations between workload dimensions, technique co-occurrence clusters, and multi-dimensional bubble charts without external data warehouse dependencies."

---

## Planned Failure Demonstrations (Resilience Features)

### 4:30 - 4:45 | Planned Failure 1: Offline AI Fallback (Network / Provider Outage Resilience)

* **Objective**: Demonstrate that external AI API rate limits, network timeouts, or cloud outages cannot compromise the core recommendation platform.
* **Execution**:
  1. Revoke or unset the `AWS_ACCESS_KEY_ID` or `GROQ_API_KEY` environment variables (or simulate network disconnect).
  2. Request an explanation via `POST /api/v1/explain` or reload the Explainability tab.
* **Observed System Behavior**:
  - The API captures the external connection failure, logs a structured warning, and activates the deterministic structured template synthesizer.
  - The response returns immediately (`HTTP 200`) with `"source": "structured"` and complete, formatted technical rationales.
  - The Prometheus metric `ai_fallback_tier{tier="structured_fallback"}` increments by 1.
* **Talking Point**:
  - "Notice that the UI never hangs, crashes, or returns an error. Our architecture enforces a three-tier resilient fallback: Bedrock -> Groq -> deterministic structured engine. Architectural advice is 100% resilient and operational in air-gapped environments."

---

### 4:45 - 5:00 | Planned Failure 2: Transactional Database Outage (OLTP Separation Resilience)

* **Objective**: Demonstrate that backend transactional database unavailability does not impair the core analytical decision pipeline.
* **Execution**:
  1. Stop the PostgreSQL database service or specify an invalid database URI in `DATABASE_URL`.
  2. Execute a full architectural recommendation run via `POST /api/v1/recommendations`.
* **Observed System Behavior**:
  - When persisting the scenario record, the database failure is caught and handled via localized fallback.
  - The core 6-stage pipeline (profiling, problem detection, candidate generation, rule evaluation, impact estimation, and architecture building) completes with zero interruption.
  - The embedded DuckDB analytics engine executes all queries directly against local Parquet files, completely independent of the operational database state.
* **Talking Point**:
  - "Our architectural decision to decouple transactional metadata persistence from embedded analytical execution (ADR 004) ensures high availability. A transient failure in our transactional store cannot paralyze the recommendation engine or block engineering decisions."

---

## 5:00 | Conclusion

* **Closing Summary**:
  - "AI Data Architect delivers deterministic, explainable, and cost-grounded infrastructure strategy."
  - "Rules make the decisions; AI provides human-readable context; real AWS list pricing grounds the budgets; Terraform accelerates implementation."
