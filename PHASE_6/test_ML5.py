"""Acceptance tests for the real ML5 risk service."""

from datetime import datetime

import pytest

from PHASE_6 import ML5


FEATURES = {
    "avg_activity": 10.0,
    "activity_growth": 0.2,
    "active_hours": 12,
    "peak_ratio": 1.5,
    "variability": 0.4,
    "internet_share": 0.7,
    "feature_timestamp": datetime(2013, 11, 7, 23),
}


def test_real_model_returns_non_stub_contract():
    result = ML5.predict(FEATURES)

    assert 0 <= result["risk_score"] <= 1
    assert result["model_version"] == "ml3-logistic-regression-v1"
    assert result["feature_timestamp"] == FEATURES["feature_timestamp"]
    assert isinstance(result["contributing_features"], list)


def test_missing_model_artifact_fails_clearly(tmp_path):
    with pytest.raises(RuntimeError, match="model artifact is missing"):
        ML5.load_model(tmp_path / "missing-model.joblib")
