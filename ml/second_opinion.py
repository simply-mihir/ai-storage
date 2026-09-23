"""Second-opinion distillation model.

NOTE: This model DISTILLS the engine; disagreement flags cases for human
review, never overrides. The rule-based engine is the sole AUTHORITY;
ML only advises.
"""

from __future__ import annotations

from storage_advisor.ml.second_opinion import (
    FEATURE_COLUMNS_V2,
    TECHNIQUE_IDS,
    RobustLogisticRegression,
    encode_features,
    encode_scenario_dict,
    format_reason_line,
    load_model,
    predict_second_opinion,
    train_distillation_model,
)

__all__ = [
    "FEATURE_COLUMNS_V2",
    "TECHNIQUE_IDS",
    "RobustLogisticRegression",
    "encode_features",
    "encode_scenario_dict",
    "format_reason_line",
    "load_model",
    "predict_second_opinion",
    "train_distillation_model",
]
