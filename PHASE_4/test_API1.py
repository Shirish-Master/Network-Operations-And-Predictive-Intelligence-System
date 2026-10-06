"""Endpoint and SQL contract tests for API1."""

import sqlite3

from fastapi.testclient import TestClient

from PHASE_4 import API1
from PHASE_4.API1_service import WAREHOUSE_DB, as_sql_timestamp, get_configured_as_of


# Endpoint tests validate the public response contract and the effective AS_OF.
def test_network_summary_matches_independent_sql_queries():
    as_of = get_configured_as_of()
    response = TestClient(API1.app).get(
        "/network/summary",
        params={"as_of": as_of.isoformat()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["as_of"] == as_of.isoformat()

    connection = sqlite3.connect(WAREHOUSE_DB)
    try:
        timestamp = as_sql_timestamp(as_of)
        expected_summary = connection.execute(
            """
            SELECT
                SUM(f.total_activity),
                COUNT(DISTINCT CASE WHEN f.total_activity > 0 THEN g.grid_id END)
            FROM fact_network_activity AS f
            JOIN dim_time AS t ON t.time_key = f.time_key
            JOIN dim_grid AS g ON g.grid_key = f.grid_key
            WHERE t.timestamp <= ?
            """,
            (timestamp,),
        ).fetchone()
        expected_peak = connection.execute(
            """
            SELECT t.hour
            FROM fact_network_activity AS f
            JOIN dim_time AS t ON t.time_key = f.time_key
            WHERE t.timestamp <= ?
            GROUP BY t.hour
            ORDER BY SUM(f.total_activity) DESC, t.hour ASC
            LIMIT 1
            """,
            (timestamp,),
        ).fetchone()[0]
        expected_grid = connection.execute(
            """
            SELECT g.grid_id
            FROM fact_network_activity AS f
            JOIN dim_time AS t ON t.time_key = f.time_key
            JOIN dim_grid AS g ON g.grid_key = f.grid_key
            WHERE t.timestamp <= ?
            GROUP BY g.grid_id
            ORDER BY SUM(f.total_activity) DESC, g.grid_id ASC
            LIMIT 1
            """,
            (timestamp,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert payload["total_activity"] == expected_summary[0]
    assert payload["active_grids"] == expected_summary[1]
    assert payload["peak_hour"] == expected_peak
    assert payload["top_grid"] == expected_grid


def test_network_summary_returns_500_when_service_is_unavailable(monkeypatch):
    def unavailable(_as_of):
        raise FileNotFoundError("warehouse unavailable")

    monkeypatch.setattr(API1, "query_network_summary", unavailable)
    response = TestClient(API1.app).get("/network/summary")

    assert response.status_code == 500
    assert "data source unavailable" in response.json()["detail"]
