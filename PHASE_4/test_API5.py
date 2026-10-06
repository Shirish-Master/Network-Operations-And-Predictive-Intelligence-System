"""Acceptance tests for the stable risk prediction contract."""

from fastapi.testclient import TestClient

from PHASE_4.API5 import app


client = TestClient(app)
VALID_REQUEST = {
    "grid_id": 1,
    "avg_activity": 10.0,
    "activity_growth": 0.2,
    "active_hours": 12,
    "peak_ratio": 1.5,
    "variability": 0.4,
    "internet_share": 0.7,
    "feature_timestamp": "2013-11-07T23:00:00",
}


def test_trained_response_contains_stable_fields_and_model_version():
    response = client.post("/network/predict-risk", json=VALID_REQUEST)

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_version"] == "ml3-logistic-regression-v1"
    assert payload["feature_timestamp"] == VALID_REQUEST["feature_timestamp"]
    assert isinstance(payload["contributing_features"], list)
    assert "stub" not in payload["explanation_note"].lower()
    assert {"risk_score", "risk_level", "model_version", "explanation_note"} <= payload.keys()


def test_missing_required_field_returns_readable_422():
    request = {**VALID_REQUEST}
    del request["avg_activity"]

    response = client.post("/network/predict-risk", json=request)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error["loc"] == ["body", "avg_activity"] for error in errors)
    assert any("required" in error["msg"].lower() for error in errors)


def test_invalid_feature_range_returns_readable_422():
    response = client.post(
        "/network/predict-risk",
        json={**VALID_REQUEST, "internet_share": 1.5},
    )

    assert response.status_code == 422
    assert "internet_share" in str(response.json()["detail"])
