"""Tests for the ML second-opinion distillation model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from storage_advisor.domain.scenario import Scenario
from storage_advisor.ml.second_opinion import (
    FEATURE_COLUMNS_V2,
    TECHNIQUE_IDS,
    load_model,
    predict_second_opinion,
    train_distillation_model,
)


def test_distillation_docstring_advisory_contract() -> None:
    """Document in docstring: this DISTILLS the engine; disagreement flags cases for human review, never overrides."""
    import storage_advisor.ml.second_opinion as mod

    doc = mod.__doc__ or ""
    assert "DISTILLS" in doc
    assert "never overrides" in doc
    assert "AUTHORITY" in doc


def test_feature_columns_v2_and_persistence() -> None:
    """FEATURE_COLUMNS_V2 constant is defined and matches persisted features_v2.json."""
    assert len(FEATURE_COLUMNS_V2) == 29
    assert "backup_frequency_per_week" in FEATURE_COLUMNS_V2
    assert "realtime_required" in FEATURE_COLUMNS_V2
    assert "ml_required" in FEATURE_COLUMNS_V2
    assert "streaming_required" in FEATURE_COLUMNS_V2

    features_path = Path("ml/features_v2.json")
    assert features_path.exists(), "ml/features_v2.json must exist"
    with open(features_path) as f:
        persisted = json.load(f)
    assert persisted == FEATURE_COLUMNS_V2


def test_training_reproduces_holdout_jaccard_ge_80() -> None:
    """Training reproduces holdout jaccard >= 0.80 at fixed seed."""
    results = train_distillation_model(
        parquet_path="data/synthetic/scenarios.parquet",
        output_dir="ml",
        random_state=42,
    )

    assert results["mean_jaccard"] >= 0.80, f"Expected mean jaccard >= 0.80, got {results['mean_jaccard']}"
    assert results["hamming_loss"] < 0.10, f"Expected hamming loss < 0.10, got {results['hamming_loss']}"
    assert Path(results["model_file"]).exists()
    assert Path(results["features_file"]).exists()


def test_predict_second_opinion_contract() -> None:
    """Predict second opinion returns recommendations, probabilities, and driver reasons."""
    scenario = Scenario(
        business_domain="FINTECH",
        company_size="LARGE",
        expected_users=500_000,
        concurrent_users=25_000,
        current_storage_gb=10_000.0,
        daily_growth_gb=50.0,
        data_types=["TRANSACTIONS"],
        structured_data_pct=80.0,
        semi_structured_data_pct=15.0,
        unstructured_data_pct=5.0,
        read_intensity="HIGH",
        write_intensity="MEDIUM",
        access_pattern="RANDOM",
        latency_requirement_ms=25.0,
        availability_requirement=99.99,
        rto_minutes=30.0,
        rpo_minutes=15.0,
        retention_years=7.0,
        budget_level="HIGH",
        analytics_required=True,
        real_time_processing_required=True,
        sensitive_data=True,
        encryption_required=True,
        compliance_requirements=["PCI_DSS", "SOC2"],
    )

    result = predict_second_opinion(scenario)
    assert "ml_recommendations" in result
    assert isinstance(result["ml_recommendations"], list)
    assert "probas" in result
    assert "driver_reasons" in result

    # Check that driver reasons exist for technique ids
    reasons = result["driver_reasons"]
    for tid in result["ml_recommendations"]:
        assert tid in reasons
        assert "Driven by" in reasons[tid]


def test_model_artifact_structure() -> None:
    """Model artifact contains chain, scaler, technique ids, and metrics."""
    artifact = load_model("ml/model.joblib")
    assert "chain" in artifact
    assert "scaler" in artifact
    assert "technique_ids" in artifact
    assert artifact["technique_ids"] == TECHNIQUE_IDS
    assert "metrics" in artifact
    assert artifact["metrics"]["mean_jaccard"] >= 0.80
