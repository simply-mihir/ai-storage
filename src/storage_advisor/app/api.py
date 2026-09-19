"""FastAPI application — REST interface to the recommendation pipeline."""

from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from storage_advisor.analytics.whatif import WhatIfAnalyzer
from storage_advisor.architecture.builder import ArchitectureBuilder
from storage_advisor.detection.problem_detector import detect_problems
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.profiling.workload_profiler import profile_workload
from storage_advisor.recommendation.recommendation_engine import run_recommendation_engine

logger = logging.getLogger("storage_advisor.api")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------

_techniques = load_techniques()
_builder = ArchitectureBuilder()
_whatif = WhatIfAnalyzer()
_start_time = time.monotonic()

KB_VERSION = "1.0.0"
ENGINE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ScenarioRequest(BaseModel):
    business_domain: str
    company_size: str = "MEDIUM"
    expected_users: int = 10_000
    concurrent_users: int = 1_000
    current_storage_gb: float = 100.0
    daily_growth_gb: float = 1.0
    data_types: list[str] = Field(default_factory=lambda: ["TEXT"])
    structured_data_pct: float = 50.0
    semi_structured_data_pct: float = 30.0
    unstructured_data_pct: float = 20.0
    read_intensity: str = "MEDIUM"
    write_intensity: str = "MEDIUM"
    access_pattern: str = "MIXED"
    latency_requirement_ms: float = 500.0
    availability_requirement: float = 99.0
    rto_minutes: float = 240.0
    rpo_minutes: float = 120.0
    retention_years: float = 1.0
    budget_level: str = "MEDIUM"
    analytics_required: bool = False
    real_time_processing_required: bool = False
    sensitive_data: bool = False
    encryption_required: bool = False
    compliance_requirements: list[str] = Field(default_factory=lambda: ["NONE"])


class RecommendationRequest(BaseModel):
    scenario_id: str = ""
    scenario: dict[str, Any] = Field(default_factory=dict)


class ExplainRequest(BaseModel):
    recommendation_id: str = ""
    recommendation: dict[str, Any] = Field(default_factory=dict)


class WhatIfRequest(BaseModel):
    baseline_scenario: dict[str, Any]
    modified_scenario: dict[str, Any]


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Data Architect",
    version=ENGINE_VERSION,
    description="Explainable AI-Powered Data Storage Architecture & Optimization Advisor",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middleware — request logging + global exception handler
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        correlation_id = str(uuid4())
        logger.error("Unhandled exception [%s]:\n%s", correlation_id, traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": "Internal error", "correlation_id": correlation_id},
        )
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s → %d (%.1f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/scenarios")
async def create_scenario(body: ScenarioRequest):
    try:
        scenario = Scenario(**body.model_dump())
    except ValidationError as e:
        errors = []
        for err in e.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
            })
        return JSONResponse(status_code=400, content={"validation_errors": errors})
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"validation_errors": [{"field": "unknown", "message": str(e), "type": "value_error"}]},
        )

    scenario_id = str(uuid4())
    return {
        "scenario_id": scenario_id,
        "normalized": scenario.model_dump(),
        "validation_errors": [],
    }


@app.post("/api/v1/recommendations")
async def get_recommendations(body: RecommendationRequest):
    start = time.perf_counter()

    try:
        scenario = Scenario(**body.scenario)
    except (ValidationError, Exception) as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid scenario: {e}"},
        )

    scenario_id = body.scenario_id or str(uuid4())

    profile = profile_workload(scenario)
    problems = detect_problems(scenario, profile)
    result = run_recommendation_engine(scenario, _techniques)
    impact = estimate_impact(scenario, result.recommendations)
    architecture = _builder.build(scenario, result)

    elapsed = (time.perf_counter() - start) * 1000
    logger.info("Recommendation pipeline completed in %.1f ms", elapsed)

    return {
        "scenario_id": scenario_id,
        "problems": [p.model_dump() for p in problems],
        "recommendations": [r.model_dump() for r in result.recommendations],
        "strategy": result.strategy.model_dump(),
        "alternatives": [a.model_dump() for a in result.alternatives],
        "impact": impact.model_dump(),
        "architecture": architecture.model_dump(),
        "engine_version": ENGINE_VERSION,
        "kb_version": KB_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/explain")
async def explain_recommendation(body: ExplainRequest):
    rec = body.recommendation

    parts = []
    if rec.get("rationale"):
        parts.append(rec["rationale"])
    if rec.get("problems_solved"):
        parts.append(f"Addresses: {', '.join(rec['problems_solved'])}.")
    if rec.get("benefits"):
        parts.append(f"Benefits: {'; '.join(rec['benefits'])}.")
    if rec.get("disadvantages"):
        parts.append(f"Trade-offs: {'; '.join(rec['disadvantages'])}.")
    if rec.get("evidence"):
        parts.append(f"Evidence: {', '.join(rec['evidence'])}.")
    if rec.get("prerequisites"):
        parts.append(f"Prerequisites: {', '.join(rec['prerequisites'])}.")

    explanation = " ".join(parts) if parts else "No explanation available for this recommendation."

    return {
        "explanation": explanation,
        "source": "structured",
    }


@app.post("/api/v1/what-if")
async def what_if(body: WhatIfRequest):
    try:
        baseline = Scenario(**body.baseline_scenario)
        modified = Scenario(**body.modified_scenario)
    except (ValidationError, Exception) as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid scenario: {e}"},
        )

    result = _whatif.compare(baseline, modified)

    return {
        "baseline_result": result.baseline.model_dump(),
        "modified_result": result.modified.model_dump(),
        "added_techniques": result.added_techniques,
        "removed_techniques": result.removed_techniques,
        "changed_priorities": result.changed_priorities,
        "storage_delta_pct": result.storage_delta_pct,
        "cost_delta_pct": result.cost_delta_pct,
        "latency_delta_pct": result.latency_delta_pct,
        "summary": result.summary,
    }


@app.get("/health")
async def health():
    try:
        uptime = time.monotonic() - _start_time
        return {
            "status": "healthy",
            "engine_version": ENGINE_VERSION,
            "kb_version": KB_VERSION,
            "kb_technique_count": len(_techniques),
            "bedrock_available": False,
            "uptime_seconds": round(uptime, 2),
        }
    except Exception:
        logger.error("Health check failed:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": "Engine initialization failed"},
        )
