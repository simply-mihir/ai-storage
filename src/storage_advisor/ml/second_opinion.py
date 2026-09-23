"""Second-opinion distillation model.

NOTE: This model DISTILLS the engine; disagreement flags cases for human
review, never overrides. The rule-based engine is the sole AUTHORITY;
ML only advises.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import hamming_loss, jaccard_score
from sklearn.model_selection import train_test_split
from sklearn.multioutput import ClassifierChain
from sklearn.preprocessing import StandardScaler

from storage_advisor.domain.scenario import Scenario, upconvert_v1
from storage_advisor.knowledge.technique_catalog import load_techniques
from storage_advisor.profiling.workload_profiler import profile_workload

logger = logging.getLogger("storage_advisor.ml")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEATURE_COLUMNS_V2: list[str] = [
    "users",
    "concurrent_users",
    "storage_size_gb",
    "daily_growth_gb",
    "latency_ms",
    "availability_pct",
    "rto_hours",
    "rpo_hours",
    "retention_years",
    "backup_frequency_per_week",
    "analytics_flag",
    "realtime_required",
    "ml_required",
    "streaming_required",
    "read_intensity",
    "write_intensity",
    "budget_tier",
    "profile_read_category",
    "profile_write_category",
    "profile_growth_category",
    "profile_scale_category",
    "domain_ai_startup",
    "domain_ecommerce",
    "domain_fintech",
    "domain_gaming",
    "domain_healthcare",
    "domain_iot",
    "domain_media",
    "domain_saas",
]

DOMAINS: list[str] = [
    "ai_startup",
    "ecommerce",
    "fintech",
    "gaming",
    "healthcare",
    "iot",
    "media",
    "saas",
]

DOMAIN_NAME_TO_KEY: dict[str, str] = {
    "AI": "ai_startup",
    "AI_STARTUP": "ai_startup",
    "ECOMMERCE": "ecommerce",
    "E_COMMERCE": "ecommerce",
    "FINTECH": "fintech",
    "FIN_TECH": "fintech",
    "GAMING": "gaming",
    "HEALTHCARE": "healthcare",
    "HEALTH_CARE": "healthcare",
    "IOT": "iot",
    "MEDIA": "media",
    "SAAS": "saas",
}

INTENSITY_MAP: dict[str, int] = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
}

GROWTH_MAP: dict[str, int] = {
    "LOW": 0,
    "MEDIUM": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "EXTREME": 4,
}

TECHNIQUE_IDS: list[str] = sorted(t.id for t in load_techniques())


# ---------------------------------------------------------------------------
# Estimator wrapper for single-class targets
# ---------------------------------------------------------------------------


class RobustLogisticRegression(LogisticRegression):
    """LogisticRegression that gracefully handles single-class target subsets."""

    def __init__(
        self,
        C: float = 1.0,
        max_iter: int = 500,
        random_state: int | None = 42,
        **kwargs: Any,
    ) -> None:
        super().__init__(C=C, max_iter=max_iter, random_state=random_state, **kwargs)
        self.constant_class_: int | None = None

    def fit(self, X: Any, y: Any, sample_weight: Any = None) -> RobustLogisticRegression:
        unique = np.unique(y)
        if len(unique) < 2:
            self.constant_class_ = int(unique[0])
            self.classes_ = np.array([0, 1])
            self.coef_ = np.zeros((1, X.shape[1]))
            self.intercept_ = np.array([10.0 if self.constant_class_ == 1 else -10.0])
            self.n_features_in_ = X.shape[1]
            return self
        return super().fit(X, y, sample_weight=sample_weight)

    def predict(self, X: Any) -> np.ndarray:
        if self.constant_class_ is not None:
            return np.full(X.shape[0], self.constant_class_)
        return super().predict(X)

    def predict_proba(self, X: Any) -> np.ndarray:
        if self.constant_class_ is not None:
            n = X.shape[0]
            if self.constant_class_ == 1:
                return np.column_stack([np.zeros(n), np.ones(n)])
            return np.column_stack([np.ones(n), np.zeros(n)])
        return super().predict_proba(X)


# ---------------------------------------------------------------------------
# Feature encoding
# ---------------------------------------------------------------------------


def encode_scenario_dict(row: dict[str, Any]) -> dict[str, float]:
    """Encode a single scenario dictionary or Scenario instance into feature values."""
    if "domain" in row and "profile_read_category" in row and "users" in row:
        # Direct parquet row format
        domain_key = str(row["domain"]).lower()
        users = float(row["users"])
        concurrent = float(row["concurrent_users"])
        storage_gb = float(row["storage_size_gb"])
        growth_gb = float(row["daily_growth_gb"])
        latency = float(row["latency_ms"])
        avail = float(row["availability_pct"])
        rto = float(row["rto_hours"])
        rpo = float(row["rpo_hours"])
        retention = float(row["retention_years"])
        backup_freq = float(row.get("backup_frequency_per_week", 7.0))
        analytics = float(int(bool(row.get("analytics_flag", False))))
        realtime = float(int(bool(row.get("realtime_required", False))))
        ml_req = float(int(bool(row.get("ml_required", False))))
        streaming = float(int(bool(row.get("streaming_required", False))))

        read_int = INTENSITY_MAP.get(str(row.get("read_intensity", "MEDIUM")).upper(), 1)
        write_int = INTENSITY_MAP.get(str(row.get("write_intensity", "MEDIUM")).upper(), 1)
        budget = INTENSITY_MAP.get(str(row.get("budget_tier", "MEDIUM")).upper(), 1)

        prof_read = INTENSITY_MAP.get(str(row.get("profile_read_category", "MEDIUM")).upper(), 1)
        prof_write = INTENSITY_MAP.get(str(row.get("profile_write_category", "MEDIUM")).upper(), 1)
        prof_growth = GROWTH_MAP.get(str(row.get("profile_growth_category", "LOW")).upper(), 0)
        prof_scale = INTENSITY_MAP.get(str(row.get("profile_scale_category", "MEDIUM")).upper(), 1)
    else:
        # Standard Scenario domain object or API payload
        scenario = Scenario(**upconvert_v1(row)) if not isinstance(row, Scenario) else row
        profile = profile_workload(scenario)

        domain_str = str(scenario.business_domain).upper()
        domain_key = DOMAIN_NAME_TO_KEY.get(domain_str, "saas")

        users = float(scenario.expected_users)
        concurrent = float(scenario.concurrent_users)
        storage_gb = float(scenario.current_storage_gb)
        growth_gb = float(scenario.daily_growth_gb)
        latency = float(scenario.latency_requirement_ms)
        avail = float(scenario.availability_requirement)

        rto = float(
            scenario.rto_hours
            if scenario.rto_hours is not None
            else scenario.rto_minutes / 60.0
        )
        rpo = float(
            scenario.rpo_hours
            if scenario.rpo_hours is not None
            else scenario.rpo_minutes / 60.0
        )
        retention = float(scenario.retention_years)
        backup_freq = float(
            scenario.backup_frequency_per_week
            if scenario.backup_frequency_per_week is not None
            else 7.0
        )

        analytics = 1.0 if scenario.analytics_required else 0.0
        realtime = 1.0 if (scenario.realtime_required or scenario.real_time_processing_required) else 0.0
        ml_req = 1.0 if scenario.ml_required else 0.0
        streaming = 1.0 if scenario.streaming_required else 0.0

        read_int = INTENSITY_MAP.get(str(scenario.read_intensity).upper(), 1)
        write_int = INTENSITY_MAP.get(str(scenario.write_intensity).upper(), 1)
        budget = INTENSITY_MAP.get(str(scenario.budget_level).upper(), 1)

        prof_read = INTENSITY_MAP.get(str(profile.read_pressure).upper(), 1)
        prof_write = INTENSITY_MAP.get(str(profile.write_pressure).upper(), 1)
        prof_growth = GROWTH_MAP.get(str(profile.storage_growth).upper(), 0)
        prof_scale = INTENSITY_MAP.get(str(profile.scalability_pressure).upper(), 1)

    feats: dict[str, float] = {
        "users": users,
        "concurrent_users": concurrent,
        "storage_size_gb": storage_gb,
        "daily_growth_gb": growth_gb,
        "latency_ms": latency,
        "availability_pct": avail,
        "rto_hours": rto,
        "rpo_hours": rpo,
        "retention_years": retention,
        "backup_frequency_per_week": backup_freq,
        "analytics_flag": analytics,
        "realtime_required": realtime,
        "ml_required": ml_req,
        "streaming_required": streaming,
        "read_intensity": float(read_int),
        "write_intensity": float(write_int),
        "budget_tier": float(budget),
        "profile_read_category": float(prof_read),
        "profile_write_category": float(prof_write),
        "profile_growth_category": float(prof_growth),
        "profile_scale_category": float(prof_scale),
    }

    for d in DOMAINS:
        feats[f"domain_{d}"] = 1.0 if domain_key == d else 0.0

    return feats


def encode_features(data: pd.DataFrame | Scenario | dict[str, Any]) -> pd.DataFrame:
    """Encode DataFrame, Scenario, or dictionary into a DataFrame with FEATURE_COLUMNS_V2."""
    if isinstance(data, pd.DataFrame):
        rows = [encode_scenario_dict(row.to_dict()) for _, row in data.iterrows()]
        df_encoded = pd.DataFrame(rows, columns=FEATURE_COLUMNS_V2)
    elif isinstance(data, Scenario):
        df_encoded = pd.DataFrame([encode_scenario_dict(data.model_dump())], columns=FEATURE_COLUMNS_V2)
    elif isinstance(data, dict):
        df_encoded = pd.DataFrame([encode_scenario_dict(data)], columns=FEATURE_COLUMNS_V2)
    else:
        raise TypeError(f"Unsupported data type for feature encoding: {type(data)}")

    return df_encoded[FEATURE_COLUMNS_V2]


def build_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Extract binary targets for all techniques from parquet dataframe."""
    targets = pd.DataFrame(index=df.index)
    parsed = df["all_technique_ids"].apply(
        lambda x: json.loads(x) if isinstance(x, str) else list(x)
    )
    for tid in TECHNIQUE_IDS:
        targets[tid] = parsed.apply(lambda rec_set, t=tid: int(t in rec_set))
    return targets


# ---------------------------------------------------------------------------
# Training & Persistence
# ---------------------------------------------------------------------------


def train_distillation_model(
    parquet_path: str = "data/synthetic/scenarios.parquet",
    output_dir: str = "ml",
    random_state: int = 42,
) -> dict[str, Any]:
    """Train second-opinion ClassifierChain model and persist artifacts.

    NOTE: This model DISTILLS the engine; disagreement flags cases for human
    review, never overrides.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(parquet_path)
    X = encode_features(df)
    Y = build_targets(df)

    stratify_col = df["domain"] if "domain" in df.columns else None
    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=0.2, random_state=random_state, stratify=stratify_col
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    chain = ClassifierChain(
        RobustLogisticRegression(random_state=random_state),
        random_state=random_state,
    )
    chain.fit(X_train_scaled, Y_train.values)

    Y_pred = chain.predict(X_test_scaled)
    hl = float(hamming_loss(Y_test.values, Y_pred))
    mean_jaccard_samples = float(jaccard_score(Y_test.values, Y_pred, average="samples"))
    mean_jaccard_macro = float(jaccard_score(Y_test.values, Y_pred, average="macro"))

    logger.info(
        "Trained distillation model: holdout hamming_loss=%.4f, mean_jaccard=%.4f",
        hl,
        mean_jaccard_samples,
    )

    # Cache top driver features per technique based on normalized linear weights
    cached_drivers: dict[str, list[str]] = {}
    for idx, tid in enumerate(TECHNIQUE_IDS):
        est = chain.estimators_[idx]
        coefs = est.coef_[0][: len(FEATURE_COLUMNS_V2)]
        top_indices = np.argsort(np.abs(coefs))[::-1][:2]
        cached_drivers[tid] = [FEATURE_COLUMNS_V2[i] for i in top_indices]

    artifact = {
        "chain": chain,
        "scaler": scaler,
        "feature_columns": FEATURE_COLUMNS_V2,
        "technique_ids": TECHNIQUE_IDS,
        "cached_drivers": cached_drivers,
        "metrics": {
            "hamming_loss": hl,
            "mean_jaccard": mean_jaccard_samples,
            "macro_jaccard": mean_jaccard_macro,
        },
        "random_state": random_state,
    }

    model_file = out_path / "model.joblib"
    features_file = out_path / "features_v2.json"

    joblib.dump(artifact, model_file)
    with open(features_file, "w") as f:
        json.dump(FEATURE_COLUMNS_V2, f, indent=2)

    return {
        "model_file": str(model_file),
        "features_file": str(features_file),
        "hamming_loss": hl,
        "mean_jaccard": mean_jaccard_samples,
        "macro_jaccard": mean_jaccard_macro,
    }


# ---------------------------------------------------------------------------
# Prediction & Explanation
# ---------------------------------------------------------------------------

_CACHED_MODEL: dict[str, Any] | None = None


def load_model(model_path: str | Path | None = None) -> dict[str, Any]:
    """Load cached model artifact."""
    global _CACHED_MODEL
    if _CACHED_MODEL is not None and model_path is None:
        return _CACHED_MODEL

    candidates = [
        Path(model_path) if model_path else None,
        Path("ml/model.joblib"),
        Path(__file__).resolve().parent / "model.joblib",
        Path(__file__).resolve().parent.parent.parent.parent / "ml" / "model.joblib",
    ]
    resolved = None
    for p in candidates:
        if p and p.exists():
            resolved = p
            break

    if resolved is None:
        raise FileNotFoundError("Could not find ml/model.joblib. Train the model first.")

    loaded = joblib.load(resolved)
    if model_path is None:
        _CACHED_MODEL = loaded
    return loaded


def format_reason_line(top_features: list[str]) -> str:
    """Format the top 2 driver features into a user-friendly one-line reason."""
    clean_names = [f.replace("_", " ").title() for f in top_features]
    if len(clean_names) >= 2:
        return f"Driven by {clean_names[0]} and {clean_names[1]}"
    if len(clean_names) == 1:
        return f"Driven by {clean_names[0]}"
    return "Driven by workload profile characteristics"


def predict_second_opinion(
    scenario: Scenario | dict[str, Any],
    model_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run ML prediction and generate driver-feature explanations.

    ML ONLY ADVISES — The deterministic engine is the sole AUTHORITY.
    Disagreements flag cases for human review.

    Returns:
        dict containing:
            - ml_recommendations: list[str] of technique IDs predicted by ML
            - probas: dict[str, float] of prediction probabilities
            - driver_reasons: dict[str, str] of one-line reasons per technique
    """
    model_artifact = load_model(model_path)
    chain: ClassifierChain = model_artifact["chain"]
    scaler: StandardScaler = model_artifact["scaler"]
    feature_cols: list[str] = model_artifact["feature_columns"]
    technique_ids: list[str] = model_artifact["technique_ids"]
    cached_drivers: dict[str, list[str]] = model_artifact.get("cached_drivers", {})

    X_df = encode_features(scenario)
    X_scaled = scaler.transform(X_df[feature_cols])

    # Base prediction & probabilities
    preds = chain.predict(X_scaled)[0]
    probas = chain.predict_proba(X_scaled)[0]

    ml_recommendations = [technique_ids[i] for i, val in enumerate(preds) if val == 1]
    probas_dict = {technique_ids[i]: round(float(p), 4) for i, p in enumerate(probas)}

    # Chain probability deltas for dynamic explanation
    # Evaluate perturbation: set each feature to mean (0.0 in scaled space)
    num_feats = X_scaled.shape[1]
    perturbed = np.repeat(X_scaled, num_feats, axis=0)
    for k in range(num_feats):
        perturbed[k, k] = 0.0

    perturbed_probas = chain.predict_proba(perturbed)
    # deltas shape: (num_feats, num_techniques)
    deltas = probas - perturbed_probas

    driver_reasons: dict[str, str] = {}
    for j, tid in enumerate(technique_ids):
        tech_deltas = deltas[:, j]
        # Check if probability deltas have non-negligible signal
        top_delta_indices = np.argsort(np.abs(tech_deltas))[::-1][:2]
        if np.max(np.abs(tech_deltas)) > 1e-4:
            top_feats = [feature_cols[idx] for idx in top_delta_indices]
        else:
            # Fall back to train-time cached top drivers
            top_feats = cached_drivers.get(tid, [feature_cols[idx] for idx in top_delta_indices])

        driver_reasons[tid] = format_reason_line(top_feats)

    return {
        "ml_recommendations": ml_recommendations,
        "probas": probas_dict,
        "driver_reasons": driver_reasons,
    }
