"""Acceptance tests for ML6 batch scoring and API3 score surfacing."""

from datetime import datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from PHASE_4 import API3
from PHASE_6 import ML6


def test_network_risk_scores_are_unique_and_versioned():
    scores = pd.read_parquet(ML6.RISK_OUTPUT)

    assert not scores.duplicated(["grid_id", "timestamp"]).any()
    assert scores["model_version"].notna().all()
    assert scores["model_version"].eq("ml3-logistic-regression-v1").all()
    assert {"grid_id", "timestamp", "risk_score", "risk_level", "model_version"} <= set(scores.columns)


def test_top_twenty_attention_report_has_attention_language():
    report = pd.read_csv(ML6.ATTENTION_OUTPUT)

    assert len(report) == 20
    assert {"grid_id", "risk_score", "attention_reason"} <= set(report.columns)
    assert report["attention_reason"].str.contains("Attention:").all()


def test_scoring_fails_cleanly_before_features_exist(tmp_path):
    with pytest.raises(FileNotFoundError, match="Cannot score before features exist"):
        ML6.read_feature_table(tmp_path / "missing-features.parquet")


def test_api3_surfaces_additive_model_fields(monkeypatch):
    timestamp = datetime(2013, 11, 2, 16)
    monkeypatch.setattr(
        API3,
        "read_risk_scores",
        lambda _as_of: {(5161, timestamp): {
            "ml_risk_score": 0.91,
            "ml_risk_label": "high",
            "model_version": "ml3-logistic-regression-v1",
        }},
    )
    response = TestClient(API3.app).get("/network/hotspots?limit=1&as_of=2013-11-07T23:00:00")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["ml_risk_score"] == 0.91
    assert item["ml_risk_label"] == "high"
    assert item["model_version"] == "ml3-logistic-regression-v1"
