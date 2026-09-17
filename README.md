# AI Data Architect

Explainable AI-Powered Data Storage Architecture & Optimization Advisor.

Given a workload scenario (scale, data types, latency requirements, compliance needs, etc.), the engine produces a coherent storage architecture with prioritized optimization recommendations, impact estimates, and explicit assumptions.

## Design Principles

- **Deterministic** — the core engine is a rules-based pipeline, not an LLM. Same input → same output, every time.
- **Explainable** — every recommendation traces: requirement → detected problem → technique → expected effect → trade-off.
- **Transparent estimates** — all impact numbers are labeled "MODEL-BASED ESTIMATE" with named assumption constants.

## Project Structure

```
src/storage_advisor/
├── domain/                    # Pydantic models
│   ├── scenario.py            # 24-field workload scenario (input)
│   ├── problems.py            # Detected architectural pressures
│   ├── techniques.py          # Technique model
│   └── recommendations.py     # Recommendation, Strategy, RecommendationResult
├── profiling/
│   └── workload_profiler.py   # Classifies scenario into discrete profiles
├── detection/
│   └── problem_detector.py    # Detects 12 problem types from scenario+profile
├── knowledge/
│   └── technique_catalog.py   # Loads 19 techniques from YAML knowledge base
├── recommendation/
│   ├── candidate_generator.py # Matches problems → techniques
│   ├── rule_engine.py         # Scores alignment, assigns priority
│   ├── conflict_resolver.py   # Hard constraints, conflicts, prerequisites
│   └── recommendation_engine.py # Pipeline orchestrator
├── estimation/
│   └── impact_estimator.py    # Storage/cost/latency impact estimates
└── exceptions.py

configs/
└── techniques.yaml            # Knowledge base: 19 technique definitions

examples/
├── sample_scenarios.json      # 6 sample workload scenarios
└── run_scenario.py            # CLI demo script

tests/                         # 113 tests across 5 files
```

## Pipeline

```
Scenario → Validation → Profiling → Problem Detection → Candidate Generation
    → Rule Evaluation → Conflict Resolution → Strategy Construction → Impact Estimation
```

See [docs/recommendation_logic.md](docs/recommendation_logic.md) for details.

## Quick Start

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run all 6 sample scenarios
python examples/run_scenario.py

# Run a specific scenario (0-based index)
python examples/run_scenario.py --scenario 0

# JSON output
python examples/run_scenario.py --json

# Run tests
pytest
```

## Sample Output

```
======================================================================
  SCENARIO: AI SaaS Platform (Baseline)
======================================================================

  Domain: AI  |  Size: LARGE
  Users: 10,000,000  |  Concurrent: 100,000
  Storage: 25,000 GB  |  Growth: 300 GB/day
  Latency: 100 ms  |  Availability: 99.99%

  DETECTED PROBLEMS (9):
    [CRITICAL] HIGH_AVAILABILITY_REQUIREMENT
    [HIGH    ] HIGH_STORAGE_GROWTH
    [HIGH    ] HIGH_READ_LATENCY
    ...

  RECOMMENDATIONS (14):
    [REQUIRED   ] Replication                  score=0.640
    [REQUIRED   ] Compression                  score=0.520
    [RECOMMENDED] Caching                      score=0.500
    ...

  IMPACT ESTIMATES [MODEL-BASED]:
    Storage: 25,000 GB -> 11,250 GB (55.0% reduction)
    Cost:    $575.00 -> $101.25/month (82.4% savings)
    Latency: 100 ms -> 21.6 ms (78.4% improvement)
```

## Documentation

- [Domain Model](docs/domain_model.md) — scenario fields, enums, validation rules
- [Recommendation Logic](docs/recommendation_logic.md) — pipeline stages, scoring, conflict resolution
- [Assumptions](docs/assumptions.md) — every impact estimation assumption with rationale

## Tech Stack

- Python 3.11+
- Pydantic v2 (validation, serialization)
- PyYAML (knowledge base)
- pytest (testing)

## Requirements

```
pydantic>=2.0
pyyaml>=6.0
```
