"""Smoke test for the ML experiment module."""

import pytest

from storage_advisor.analytics.ml_experiment import MLResult, run_experiment


@pytest.fixture(scope="module")
def ml_result():
    return run_experiment("data/synthetic/scenarios.parquet")


class TestRunExperiment:
    def test_completes_without_error(self, ml_result):
        assert isinstance(ml_result, MLResult)

    def test_all_fields_populated(self, ml_result):
        assert len(ml_result.feature_names) > 0
        assert len(ml_result.target_technique_ids) == 19
        assert ml_result.train_size > 0
        assert ml_result.test_size > 0
        assert len(ml_result.per_technique_metrics) == 19
        assert len(ml_result.feature_importances) > 0

    def test_macro_f1_in_range(self, ml_result):
        assert 0.0 <= ml_result.macro_f1 <= 1.0

    def test_rule_agreement_in_range(self, ml_result):
        assert 0.0 <= ml_result.rule_agreement_rate <= 1.0
