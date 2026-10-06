"""Acceptance tests for the chronological ML3 baseline."""

import json

from PHASE_6.ML3 import REPORT_OUTPUT, chronological_split, prepare_training_data


def test_train_and_test_ranges_do_not_overlap():
    train, test = chronological_split(prepare_training_data())

    assert train["feature_timestamp"].max() < test["feature_timestamp"].min()


def test_report_contains_base_rate_and_separate_metrics():
    report = json.loads(REPORT_OUTPUT.read_text(encoding="utf-8"))
    metrics = report["metrics"]

    assert "accuracy" in metrics
    assert "base_rate" in metrics
    assert "precision" in metrics
    assert "recall" in metrics
    assert 0 <= metrics["base_rate"] <= 1
    assert len(report["observations"]) == 3
    assert any("limited" in observation.lower() for observation in report["observations"])


def test_model_report_includes_coefficients_and_np3_comparison():
    report = json.loads(REPORT_OUTPUT.read_text(encoding="utf-8"))

    assert set(report["coefficients"]) == {
        "avg_activity",
        "activity_growth",
        "active_hours",
        "peak_ratio",
        "variability",
        "internet_share",
    }
    assert {"overlap", "model_only", "np3_only"} <= set(report["np3_comparison"])
