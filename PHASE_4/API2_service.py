"""Service layer for one grid's hourly analytics."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = BASE_DIR / "data" / "analytics" / "warehouse.db"


def query_grid_activity(
    connection: sqlite3.Connection,
    grid_id: int,
    start_timestamp: str,
    end_timestamp: str,
    selected_date: date | None = None,
    selected_hour: int | None = None,
) -> list[sqlite3.Row]:
    """Read one row per grid/hour from the warehouse."""
    filters = ["g.grid_id = ?", "t.timestamp BETWEEN ? AND ?"]
    parameters: list[Any] = [grid_id, start_timestamp, end_timestamp]
    if selected_date is not None:
        filters.append("t.date = ?")
        parameters.append(selected_date.isoformat())
    if selected_hour is not None:
        filters.append("t.hour = ?")
        parameters.append(selected_hour)

    return connection.execute(
        f"""
        SELECT
            t.timestamp,
            f.total_activity,
            f.total_sms_activity,
            f.total_call_activity,
            f.internet_activity
        FROM fact_network_activity AS f
        JOIN dim_time AS t ON t.time_key = f.time_key
        JOIN dim_grid AS g ON g.grid_key = f.grid_key
        WHERE {' AND '.join(filters)}
        ORDER BY t.timestamp ASC
        """,
        parameters,
    ).fetchall()


def validate_grid_activity_sql(
    connection: sqlite3.Connection,
    grid_id: int,
    start_timestamp: str,
    end_timestamp: str,
    selected_date: date | None,
    selected_hour: int | None,
    rows: list[sqlite3.Row],
) -> None:
    """Reconcile response count, timestamps, and totals with independent SQL."""
    filters = ["g.grid_id = ?", "t.timestamp BETWEEN ? AND ?"]
    parameters: list[Any] = [grid_id, start_timestamp, end_timestamp]
    if selected_date is not None:
        filters.append("t.date = ?")
        parameters.append(selected_date.isoformat())
    if selected_hour is not None:
        filters.append("t.hour = ?")
        parameters.append(selected_hour)

    count, distinct_timestamps, total = connection.execute(
        f"""
        SELECT COUNT(*), COUNT(DISTINCT t.timestamp), COALESCE(SUM(f.total_activity), 0)
        FROM fact_network_activity AS f
        JOIN dim_time AS t ON t.time_key = f.time_key
        JOIN dim_grid AS g ON g.grid_key = f.grid_key
        WHERE {' AND '.join(filters)}
        """,
        parameters,
    ).fetchone()
    response_timestamps = [row[0] for row in rows]
    if count != len(rows) or distinct_timestamps != len(response_timestamps):
        raise RuntimeError("Grid activity response contains duplicate or missing hourly rows")
    if abs(float(total) - sum(float(row[1]) for row in rows)) > 1e-6:
        raise RuntimeError("Grid activity response failed SQL total validation")
