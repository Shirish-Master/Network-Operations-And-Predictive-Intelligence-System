"""Acceptance tests for ML4 anomaly scores and three-way comparison."""

import json

import pandas as pd

from PHASE_6.ML4 import (
    ANOMALY_OUTPUT,
    COMPARISON_OUTPUT,
    REPORT_OUTPUT,
    build_historical_baseline,
)


def test_hour_of_day_baseline_uses_multiple_days():
    scores = pd.read_parquet(ANOMALY_OUTPUT)
    bucket_counts = scores.assign(hour_of_day=pd.to_datetime(scores["timestamp"]).dt.hour).groupby(["grid_id", "hour_of_day"]).size()

    assert bucket_counts.min() > 1


def test_high_and_low_anomalies_have_direction():
    scores = pd.read_parquet(ANOMALY_OUTPUT)
    flagged = scores[scores["anomaly_flag"]]

    assert "high" in set(flagged["direction"])
    assert "low" in set(flagged["direction"])
    assert flagged["reason"].notna().all()


def test_three_way_comparison_has_a_genuine_explained_disagreement():
    comparison = pd.read_csv(COMPARISON_OUTPUT)
    report = json.loads(REPORT_OUTPUT.read_text(encoding="utf-8"))

    assert {"anomaly_flag", "ml3_positive", "np3_alert"} <= set(comparison.columns)
    assert report["three_way_comparison"]["example_disagreement"] is not None
    assert report["three_way_comparison"]["example_disagreement"]["disagreement_reason"]


def test_ml4_reuses_np3_baseline_function():
    source = build_historical_baseline.__code__.co_names
    assert "build_baseline" in source
