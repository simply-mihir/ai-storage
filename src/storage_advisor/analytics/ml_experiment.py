"""ML experiment — trains classifiers on the synthetic dataset and compares
predictions to the deterministic rule engine.

All results are trained on synthetic data, not production measurements.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

from storage_advisor.knowledge.technique_catalog import load_techniques

TECHNIQUE_IDS = sorted(t.id for t in load_techniques())

_LABEL_ENCODE_COLS = [
    "read_intensity",
    "write_intensity",
    "profile_scale_category",
    "profile_growth_category",
]

_NUMERIC_FEATURES = [
    "users",
    "daily_growth_gb",
    "storage_size_gb",
    "latency_ms",
    "availability_pct",
    "rto_hours",
    "rpo_hours",
    "retention_years",
    "analytics_flag",
]


@dataclass
class MLResult:
    feature_names: list[str]
    target_technique_ids: list[str]
    train_size: int
    test_size: int
    per_technique_metrics: pd.DataFrame
    macro_f1: float
    rule_agreement_rate: float
    feature_importances: pd.DataFrame


def _build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    features = df[_NUMERIC_FEATURES].copy()
    features["analytics_flag"] = features["analytics_flag"].astype(int)

    encoders: dict[str, LabelEncoder] = {}
    for col in _LABEL_ENCODE_COLS:
        le = LabelEncoder()
        features[col] = le.fit_transform(df[col])
        encoders[col] = le

    domain_dummies = pd.get_dummies(df["domain"], prefix="domain", dtype=int)
    features = pd.concat([features, domain_dummies], axis=1)

    return features, list(features.columns)


def _build_targets(df: pd.DataFrame) -> pd.DataFrame:
    targets = pd.DataFrame(index=df.index)
    parsed = df["all_technique_ids"].apply(json.loads)
    for tid in TECHNIQUE_IDS:
        targets[tid] = parsed.apply(lambda ids, t=tid: int(t in ids))
    return targets


def _rule_top5(row_json: str) -> set[str]:
    ids = json.loads(row_json)
    return set(ids[:5])


def _ml_top5(probas: np.ndarray, technique_ids: list[str]) -> set[str]:
    top_indices = np.argsort(probas)[::-1][:5]
    return {technique_ids[i] for i in top_indices}


def run_experiment(
    parquet_path: str = "data/synthetic/scenarios.parquet",
) -> MLResult:
    print("=" * 70)
    print("ML EXPERIMENT — trained on synthetic data, not production measurements")
    print("=" * 70)

    df = pd.read_parquet(parquet_path)
    X, feature_names = _build_features(df)
    Y = _build_targets(df)

    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=0.2, stratify=df["domain"], random_state=42,
    )
    test_indices = X_test.index

    print(f"\nTrain size: {len(X_train)}  |  Test size: {len(X_test)}")
    print(f"Features: {len(feature_names)}  |  Targets: {len(TECHNIQUE_IDS)}")

    # --- Logistic Regression (baseline) ---
    # Some targets may be single-class (e.g. replication in 100% of scenarios).
    # Filter those out for LR; RF handles them natively.
    varying_cols = [c for c in TECHNIQUE_IDS if Y_train[c].nunique() > 1]
    print(f"\nTraining LogisticRegression ({len(varying_cols)}/{len(TECHNIQUE_IDS)} varying targets)...")
    lr = MultiOutputClassifier(
        make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, random_state=42),
        ),
    )
    lr.fit(X_train, Y_train[varying_cols])

    # --- Random Forest (primary) ---
    print("Training RandomForest...")
    rf = MultiOutputClassifier(
        RandomForestClassifier(n_estimators=100, random_state=42),
    )
    rf.fit(X_train, Y_train)

    # --- Per-technique metrics ---
    Y_pred = rf.predict(X_test)
    Y_pred_df = pd.DataFrame(Y_pred, columns=TECHNIQUE_IDS, index=test_indices)

    rows = []
    for i, tid in enumerate(TECHNIQUE_IDS):
        y_true = Y_test[tid].values
        y_pred = Y_pred_df[tid].values

        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        rows.append({
            "technique_id": tid,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        })

    metrics_df = pd.DataFrame(rows)

    # --- Rule agreement ---
    probas_list = []
    for est in rf.estimators_:
        proba = est.predict_proba(X_test)
        if proba.shape[1] == 1:
            # Single-class target: all samples belong to that class
            probas_list.append(np.ones(len(X_test)) if est.classes_[0] == 1 else np.zeros(len(X_test)))
        else:
            probas_list.append(proba[:, 1])
    probas_matrix = np.column_stack(probas_list)

    agree_count = 0
    for idx_pos, df_idx in enumerate(test_indices):
        rule_set = _rule_top5(df.loc[df_idx, "all_technique_ids"])
        ml_set = _ml_top5(probas_matrix[idx_pos], TECHNIQUE_IDS)
        if len(rule_set & ml_set) >= 3:
            agree_count += 1

    rule_agreement_rate = agree_count / len(X_test)

    per_technique_agreement = []
    for i, tid in enumerate(TECHNIQUE_IDS):
        y_true = Y_test[tid].values
        y_pred = Y_pred_df[tid].values
        agreement = (y_true == y_pred).mean()
        per_technique_agreement.append(round(agreement, 4))

    metrics_df["rule_agreement"] = per_technique_agreement

    # --- Feature importances ---
    importances = np.mean(
        [est.feature_importances_ for est in rf.estimators_], axis=0,
    )
    importance_df = pd.DataFrame({
        "feature": feature_names,
        "importance": np.round(importances, 4),
    }).sort_values("importance", ascending=False).reset_index(drop=True)

    macro_f1 = round(float(metrics_df["f1"].mean()), 4)

    metrics_df = metrics_df.sort_values("f1", ascending=False).reset_index(drop=True)

    # --- Print results ---
    print(f"\n{'Technique':<25} {'Precision':>10} {'Recall':>8} {'F1':>8} {'Rule Agr.':>10}")
    print("-" * 65)
    for _, r in metrics_df.iterrows():
        print(
            f"{r['technique_id']:<25} {r['precision']:>10.4f} {r['recall']:>8.4f} "
            f"{r['f1']:>8.4f} {r['rule_agreement']:>10.4f}"
        )

    print(f"\nMacro F1:             {macro_f1:.4f}")
    print(f"Rule agreement rate:  {rule_agreement_rate:.4f} "
          f"(top-5 overlap >= 3)")

    print(f"\nTop 10 features by importance:")
    for _, r in importance_df.head(10).iterrows():
        print(f"  {r['feature']:<35} {r['importance']:.4f}")

    result = MLResult(
        feature_names=feature_names,
        target_technique_ids=TECHNIQUE_IDS,
        train_size=len(X_train),
        test_size=len(X_test),
        per_technique_metrics=metrics_df,
        macro_f1=macro_f1,
        rule_agreement_rate=round(rule_agreement_rate, 4),
        feature_importances=importance_df,
    )

    return result
