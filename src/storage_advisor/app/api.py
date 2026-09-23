"""FastAPI application — REST interface to the recommendation pipeline."""

from __future__ import annotations

import logging
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from storage_advisor.analytics.whatif import WhatIfAnalyzer
from storage_advisor.architecture.builder import ArchitectureBuilder
from storage_advisor.db.record import save_scenario
from storage_advisor.detection.problem_detector import detect_problems
from storage_advisor.domain.scenario import Scenario, upconvert_v1
from storage_advisor.estimation.impact_estimator import estimate_impact
from storage_advisor.integrations.bedrock import BedrockExplainer
from storage_advisor.integrations.pricing import AWSPricingClient
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.profiling.workload_profiler import profile_workload
from storage_advisor.recommendation.recommendation_engine import (
    run_recommendation_engine,
)
from storage_advisor.reports.builder import build_report
from storage_advisor.reports.export import render_markdown, render_pdf

logger = logging.getLogger("storage_advisor.api")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------

_techniques = load_techniques()
_builder = ArchitectureBuilder()
_whatif = WhatIfAnalyzer()
_explainer = BedrockExplainer()
_pricing = AWSPricingClient()
_start_time = time.monotonic()

KB_VERSION = "1.0.0"
ENGINE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ScenarioRequest(BaseModel):
    schema_version: int = 1
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
    rto_hours: float | None = None
    rpo_hours: float | None = None
    backup_frequency_per_week: int | None = None
    realtime_required: bool = False
    ml_required: bool = False
    streaming_required: bool = False


class RecommendationRequest(BaseModel):
    scenario_id: str = ""
    scenario: dict[str, Any] = Field(default_factory=dict)


class ExplainRequest(BaseModel):
    recommendation_id: str = ""
    recommendation: dict[str, Any] = Field(default_factory=dict)
    scenario: dict[str, Any] = Field(default_factory=dict)


class WhatIfRequest(BaseModel):
    baseline_scenario: dict[str, Any]
    modified_scenario: dict[str, Any]


class RealCostRequest(BaseModel):
    scenario: dict[str, Any]
    architecture: dict[str, Any] = Field(default_factory=dict)


class TrajectoryRequest(BaseModel):
    scenario: dict[str, Any]
    months: int = Field(default=24, ge=1, le=60)
    user_growth_rate: float = Field(default=0.05, ge=0.0, le=1.0)


class TerraformRequest(BaseModel):
    scenario: dict[str, Any]
    architecture: dict[str, Any] = Field(default_factory=dict)


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
    except Exception:  # noqa: BLE001
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
        scenario = Scenario(**upconvert_v1(body.model_dump()))
    except ValidationError as e:
        errors = []
        for err in e.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type": err["type"],
            })
        return JSONResponse(status_code=400, content={"validation_errors": errors})
    except (ValueError, KeyError, TypeError) as e:
        return JSONResponse(
            status_code=400,
            content={"validation_errors": [{"field": "unknown", "message": str(e), "type": "value_error"}]},
        )

    scenario_id = str(uuid4())
    save_scenario(scenario_id, scenario.model_dump())
    return {
        "scenario_id": scenario_id,
        "normalized": scenario.model_dump(),
        "validation_errors": [],
    }


@app.post("/api/v1/recommendations")
async def get_recommendations(body: RecommendationRequest):
    start = time.perf_counter()

    try:
        scenario = Scenario(**upconvert_v1(body.scenario))
    except (ValidationError, ValueError, KeyError, TypeError) as e:
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
        "generated_at": datetime.now(UTC).isoformat(),
    }


@app.post("/api/v1/explain")
async def explain_recommendation(body: ExplainRequest):
    if body.scenario:
        try:
            scenario = Scenario(**upconvert_v1(body.scenario))
            result = run_recommendation_engine(scenario, _techniques)
            impact = estimate_impact(scenario, result.recommendations)
            explanation = _explainer.explain(result, scenario, impact)
            return {"explanation": explanation.text, "source": explanation.source}
        except Exception as e:  # noqa: BLE001
            logger.warning("Bedrock explain path failed, falling back to structured: %s", e)

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

    return {"explanation": explanation, "source": "structured"}


@app.post("/api/v1/what-if")
async def what_if(body: WhatIfRequest):
    try:
        baseline = Scenario(**upconvert_v1(body.baseline_scenario))
        modified = Scenario(**upconvert_v1(body.modified_scenario))
    except (ValidationError, ValueError, KeyError, TypeError) as e:
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


@app.get("/api/v1/pricing")
async def get_pricing(region: str = "us-east-1"):
    client = AWSPricingClient(region=region) if region != _pricing.region else _pricing
    return {
        "s3_per_gb": client.get_s3_price_per_gb(),
        "elasticache_per_hour": client.get_elasticache_price_per_hour(),
        "rds_per_hour": client.get_rds_price_per_hour(),
        "glacier_per_gb": client.get_glacier_price_per_gb(),
        "source": "aws_list_price",
        "region": region,
        "retrieved_at": datetime.now(UTC).isoformat(),
    }


@app.post("/api/v1/real-cost")
async def real_cost(body: RealCostRequest):
    try:
        scenario = Scenario(**upconvert_v1(body.scenario))
    except (ValidationError, ValueError, KeyError, TypeError) as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid scenario: {e}"})

    if body.architecture:
        from storage_advisor.architecture.builder import ArchitectureOutput
        architecture = ArchitectureOutput(**body.architecture)
    else:
        result = run_recommendation_engine(scenario, _techniques)
        architecture = _builder.build(scenario, result)

    estimate = _pricing.calculate_monthly_architecture_cost(architecture, scenario)
    return {
        "line_items": [
            {
                "component": li.component,
                "service": li.service,
                "label": li.label,
                "monthly_cost_usd": li.monthly_cost_usd,
                "unit_price": li.unit_price,
                "unit": li.unit,
                "quantity": li.quantity,
            }
            for li in estimate.line_items
        ],
        "total_monthly_usd": estimate.total_monthly_usd,
        "region": estimate.region,
        "pricing_date": estimate.pricing_date,
        "source": estimate.source,
        "disclaimer": estimate.disclaimer,
    }


@app.post("/api/v1/trajectory")
async def trajectory(body: TrajectoryRequest):
    try:
        scenario = Scenario(**upconvert_v1(body.scenario))
    except (ValidationError, ValueError, KeyError, TypeError) as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid scenario: {e}"})

    from storage_advisor.analytics.trajectory import GrowthTrajectorySimulator
    simulator = GrowthTrajectorySimulator()
    result = simulator.simulate(
        scenario, months=body.months, user_growth_rate=body.user_growth_rate,
    )

    return {
        "months_simulated": result.months_simulated,
        "architecture_stable_until": result.architecture_stable_until,
        "tipping_points": [
            {
                "month": tp.month,
                "trigger": tp.trigger,
                "old_state": tp.old_state,
                "new_state": tp.new_state,
                "technique_id": tp.technique_id,
                "severity": tp.severity,
                "description": tp.description,
            }
            for tp in result.tipping_points
        ],
        "cost_at_month_1": result.starting_cost_usd,
        "cost_at_month_24": result.ending_cost_usd,
        "summary": result.summary,
        "snapshots": [
            {
                "month": s.month,
                "users": s.users,
                "storage_gb": s.storage_gb,
                "problems": s.problems,
                "top_techniques": s.top_techniques,
                "required_techniques": s.required_techniques,
                "architecture_services": s.architecture_services,
                "estimated_storage_gb": s.estimated_storage_gb,
                "real_cost_usd": s.real_cost_usd,
                "latency_ms": s.latency_ms,
            }
            for s in result.snapshots
        ],
    }


@app.post("/api/v1/export/terraform")
async def export_terraform(body: TerraformRequest):
    try:
        scenario = Scenario(**upconvert_v1(body.scenario))
    except (ValidationError, ValueError, KeyError, TypeError) as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid scenario: {e}"})

    if body.architecture:
        from storage_advisor.architecture.builder import ArchitectureOutput
        architecture = ArchitectureOutput(**body.architecture)
    else:
        result = run_recommendation_engine(scenario, _techniques)
        architecture = _builder.build(scenario, result)

    from storage_advisor.export.terraform import TerraformGenerator
    gen = TerraformGenerator()
    export = gen.generate(scenario, architecture)

    return {
        "files": export.files,
        "resource_count": export.resource_count,
        "component_count": export.component_count,
        "summary": export.summary,
    }


class ReportRequest(BaseModel):
    scenario: dict[str, Any]


@app.post("/api/v1/report")
async def generate_report(body: ReportRequest):
    try:
        scenario = Scenario(**upconvert_v1(body.scenario))
    except (ValidationError, ValueError, KeyError, TypeError) as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid scenario: {e}"},
        )

    payload = build_report(scenario)
    return payload.model_dump()


@app.get("/api/v1/report/export")
async def export_report(
    format: str = "md",
    business_domain: str = "AI",
    company_size: str = "ENTERPRISE",
    expected_users: int = 10_000,
    concurrent_users: int = 1_000,
    current_storage_gb: float = 100.0,
    daily_growth_gb: float = 1.0,
    read_intensity: str = "HIGH",
    write_intensity: str = "HIGH",
    access_pattern: str = "MIXED",
    latency_requirement_ms: float = 100.0,
    availability_requirement: float = 99.99,
    rto_minutes: float = 60.0,
    rpo_minutes: float = 15.0,
    retention_years: float = 7.0,
    budget_level: str = "HIGH",
):
    try:
        scenario = Scenario(**upconvert_v1({
            "business_domain": business_domain,
            "company_size": company_size,
            "expected_users": expected_users,
            "concurrent_users": concurrent_users,
            "current_storage_gb": current_storage_gb,
            "daily_growth_gb": daily_growth_gb,
            "data_types": ["TEXT"],
            "structured_data_pct": 50.0,
            "semi_structured_data_pct": 30.0,
            "unstructured_data_pct": 20.0,
            "read_intensity": read_intensity,
            "write_intensity": write_intensity,
            "access_pattern": access_pattern,
            "latency_requirement_ms": latency_requirement_ms,
            "availability_requirement": availability_requirement,
            "rto_minutes": rto_minutes,
            "rpo_minutes": rpo_minutes,
            "retention_years": retention_years,
            "budget_level": budget_level,
            "analytics_required": False,
            "real_time_processing_required": False,
            "sensitive_data": False,
            "encryption_required": False,
            "compliance_requirements": ["NONE"],
        }))
    except (ValidationError, ValueError, KeyError, TypeError) as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid parameters: {e}"},
        )

    payload = build_report(scenario)

    if format == "pdf":
        pdf_bytes = render_pdf(payload)
        return JSONResponse(
            status_code=200,
            content={"data": pdf_bytes.hex(), "format": "pdf", "encoding": "hex"},
            headers={"Content-Type": "application/json"},
        )

    md_text = render_markdown(payload)
    return JSONResponse(
        status_code=200,
        content={"data": md_text, "format": "md"},
    )


_STATIC_DIR = Path(__file__).resolve().parents[3] / "static"
if not _STATIC_DIR.exists():
    _STATIC_DIR = Path("/app/static")


@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")


if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    try:
        uptime = time.monotonic() - _start_time
        return {
            "status": "healthy",
            "engine_version": ENGINE_VERSION,
            "kb_version": KB_VERSION,
            "kb_technique_count": len(_techniques),
            "bedrock_available": _explainer.available,
            "groq_available": _explainer.groq_available,
            "uptime_seconds": round(uptime, 2),
        }
    except Exception:  # noqa: BLE001
        logger.error("Health check failed:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": "Engine initialization failed"},
        )
