"""Acceptance tests for the stored ML2 feature API."""

import pandas as pd
from fastapi.testclient import TestClient

from PHASE_4 import API4


client = TestClient(API4.app)
EXPECTED_FEATURES = {
    "avg_activity",
    "activity_growth",
    "active_hours",
    "peak_ratio",
    "variability",
    "internet_share",
    "feature_timestamp",
}


def test_feature_names_and_metadata_are_stable():
    response = client.get("/network/grid/1/features")

    assert response.status_code == 200
    payload = response.json()
    assert EXPECTED_FEATURES.issubset(payload)
    assert payload["data_quality_status"] == "valid"
    assert payload["feature_freshness"] in {"current", "stale"}


def test_response_matches_stored_feature_table():
    response = client.get("/network/grid/1/features")
    assert response.status_code == 200
    payload = response.json()
    stored = pd.read_parquet(API4.FEATURE_TABLE)
    row = stored.loc[stored["grid_id"] == 1].sort_values("feature_timestamp").iloc[-1]

    for field in EXPECTED_FEATURES - {"feature_timestamp"}:
        assert payload[field] == row[field]
    assert payload["feature_timestamp"] == pd.Timestamp(row["feature_timestamp"]).isoformat()


def test_grid_without_stored_features_returns_clear_error(monkeypatch, tmp_path):
    empty_features = tmp_path / "empty.parquet"
    pd.DataFrame(columns=["grid_id", *EXPECTED_FEATURES]).to_parquet(empty_features, index=False)
    monkeypatch.setattr(API4, "FEATURE_TABLE_CANDIDATES", (empty_features,))

    response = client.get("/network/grid/10000/features")

    assert response.status_code == 500
    assert "No stored features found" in response.json()["detail"]
