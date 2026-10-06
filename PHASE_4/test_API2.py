"""Endpoint and SQL contract tests for API2."""

import sqlite3

from fastapi.testclient import TestClient

from PHASE_4 import API2
from PHASE_4.API1_service import as_sql_timestamp, get_configured_as_of
from PHASE_4.API2_service import WAREHOUSE_DB


# Acceptance criteria: grid 4821 returns exactly 24 points for the default window.
def test_grid_4821_default_window_has_24_unique_points():
    response = TestClient(API2.app).get("/network/grid/4821")

    assert response.status_code == 200
    points = response.json()["activity"]
    assert len(points) == 24
    assert len({point["timestamp"] for point in points}) == 24


# Acceptance criteria: grid_id 0 and 10001 both return 404.
def test_out_of_range_grids_return_404():
    client = TestClient(API2.app)
    assert client.get("/network/grid/0").status_code == 404
    assert client.get("/network/grid/10001").status_code == 404


def test_optional_filters_are_validated():
    client = TestClient(API2.app)
    assert client.get("/network/grid/4821?hour=24").status_code == 422
    assert client.get("/network/grid/4821?date=not-a-date").status_code == 422


# Acceptance criteria: values match the warehouse exactly for a spot-checked hour.
def test_spot_checked_hour_matches_warehouse():
    as_of = get_configured_as_of()
    response = TestClient(API2.app).get(
        "/network/grid/4821",
        params={"as_of": as_of.isoformat()},
    )
    assert response.status_code == 200
    point = response.json()["activity"][0]

    connection = sqlite3.connect(WAREHOUSE_DB)
    try:
        row = connection.execute(
            """
            SELECT
                t.timestamp,
                f.total_activity,
                f.total_sms_activity,
                f.total_call_activity,
                f.internet_activity
            FROM fact_network_activity AS f
            JOIN dim_time AS t ON t.time_key = f.time_key
            JOIN dim_grid AS g ON g.grid_key = f.grid_key
            WHERE g.grid_id = ? AND t.timestamp = ?
            """,
            (4821, point["timestamp"].replace("T", " ")),
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert point["timestamp"] == row[0].replace(" ", "T")
    assert point["total_activity"] == row[1]
    assert point["sms_activity"] == row[2]
    assert point["call_activity"] == row[3]
    assert point["internet_activity"] == row[4]


def test_default_window_ends_at_dynamic_as_of():
    response = TestClient(API2.app).get("/network/grid/4821")
    assert response.status_code == 200
    payload = response.json()
    assert payload["activity"][-1]["timestamp"] <= payload["as_of"]
    assert payload["as_of"] == get_configured_as_of().isoformat()
