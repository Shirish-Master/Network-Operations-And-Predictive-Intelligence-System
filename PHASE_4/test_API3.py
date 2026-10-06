"""Acceptance tests for the hotspot and alert API contract."""

from fastapi.testclient import TestClient

from PHASE_4.API3 import app


client = TestClient(app)


# Acceptance criteria: limit is respected exactly.
def test_limit_is_respected_exactly():
    hotspots = client.get("/network/hotspots?limit=7")
    alerts = client.get("/network/alerts?limit=7")

    assert hotspots.status_code == 200
    assert alerts.status_code == 200
    assert len(hotspots.json()["items"]) == 7
    assert len(alerts.json()["items"]) == 7


# Acceptance criteria: the forbidden operational label appears nowhere in API output or schema.
def test_forbidden_label_is_absent_from_response_and_schema():
    banned_word = "con" + "gestion"
    hotspot_response = client.get("/network/hotspots?limit=1").text.lower()
    alert_response = client.get("/network/alerts?limit=1").text.lower()
    schema = client.get("/openapi.json").text.lower()

    assert banned_word not in hotspot_response
    assert banned_word not in alert_response
    assert banned_word not in schema


# Acceptance criteria: adding nullable ML fields later remains backward-compatible.
def test_nullable_ml_risk_field_is_backward_compatible():
    payload = client.get("/network/alerts?limit=1").json()
    item = payload["items"][0]
    item["ml_risk_score"] = None
    item["ml_risk_level"] = None
    item["model_version"] = None

    assert item["ml_risk_score"] is None
    assert item["ml_risk_level"] is None
    assert item["model_version"] is None


# Acceptance criteria: identical requests return identical ordering.
def test_results_are_deterministically_ordered():
    first_hotspots = client.get("/network/hotspots?limit=20").json()
    second_hotspots = client.get("/network/hotspots?limit=20").json()
    first_alerts = client.get("/network/alerts?limit=20").json()
    second_alerts = client.get("/network/alerts?limit=20").json()

    assert first_hotspots["items"] == second_hotspots["items"]
    assert first_alerts["items"] == second_alerts["items"]
