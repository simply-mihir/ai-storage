# ML Second-Opinion Model

Distillation model that mirrors the deterministic rule engine's outputs. Disagreement flags cases for human review — ML never overrides the engine.

## Regeneration

```bash
.venv/bin/python -c "from storage_advisor.ml.second_opinion import train_distillation_model; train_distillation_model()"
```

This reads `data/synthetic/scenarios.parquet`, trains a `ClassifierChain(LogisticRegression)`, and writes `ml/model.joblib` + `ml/features_v2.json`.

## Feature columns

Defined in `src/storage_advisor/ml/second_opinion.py:FEATURE_COLUMNS_V2` and persisted to `ml/features_v2.json` (29 features).

## Expected holdout metric

At `random_state=42` with 80/20 stratified split: mean Jaccard (samples) >= 0.80.
