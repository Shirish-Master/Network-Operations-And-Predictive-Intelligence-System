"""Focused tests for the Phase 4 pipeline and grid evidence API."""

import json
from datetime import datetime

from fastapi.testclient import TestClient

from PHASE_4 import API6
from PHASE_4 import API1


# 5. Add tests, including a test that /pipeline/status correctly reports unhealthy after a deliberately failed run.
def test_pipeline_status_reports_unhealthy_after_failed_run(tmp_path, monkeypatch):
    status_file = tmp_path / "pipeline_status.json"
    status_file.write_text(
        json.dumps(
            {
                "pipeline": "telecom_end_to_end",
                "run_id": "failed-run-1",
                "timestamp": datetime.now().isoformat(),
                "status": "FAILED",
                "failure_type": "WAREHOUSE_LOAD_FAILURE",
                "processed_exists": True,
                "warehouse_exists": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(API6, "STATUS_FILE", status_file)
    monkeypatch.setattr(API6, "get_configured_as_of", lambda: datetime(2013, 11, 7, 23))

    response = TestClient(API6.app).get("/pipeline/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["healthy"] is False
    assert payload["last_run_id"] == "failed-run-1"
    assert payload["reasons"]
    assert "warehouse is unavailable" in payload["reasons"]


def test_grid_location_does_not_return_polygon_geometry():
    response = TestClient(API6.app).get("/network/grid/4821/location")

    assert response.status_code == 200
    payload = response.json()
    assert payload["grid_id"] == 4821
    assert 45.0 <= payload["centroid_latitude"] <= 46.5
    assert 8.5 <= payload["centroid_longitude"] <= 10.5
    assert set(payload) == {
        "grid_id",
        "centroid_latitude",
        "centroid_longitude",
        "polygon_reference",
    }
    assert "geometry" not in payload


def test_pipeline_status_as_of_matches_api1():
    api1_as_of = API1.get_configured_as_of()
    response = TestClient(API6.app).get("/pipeline/status")

    assert response.status_code == 200
    assert response.json()["as_of"] == api1_as_of.isoformat()