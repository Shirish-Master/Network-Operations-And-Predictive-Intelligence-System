"""Service layer for the curated network summary."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pyarrow.dataset as ds


BASE_DIR = Path(__file__).resolve().parents[1]
WAREHOUSE_DB = BASE_DIR / "data" / "analytics" / "warehouse.db"
ANALYTICS_PATH = BASE_DIR / "data" / "analytics" / "hourly_grid_summary"


def get_configured_as_of() -> datetime:
    """Return the maximum timestamp from the persisted analytics layer."""
    if ANALYTICS_PATH.exists():
        analytics_table = ds.dataset(str(ANALYTICS_PATH), format="parquet")
        timestamps = analytics_table.to_table(columns=["timestamp"]).column("timestamp")
        if len(timestamps) == 0:
            raise ValueError("Analytics source contains no timestamps")
        return max(value.as_py() for value in timestamps)

    if not WAREHOUSE_DB.exists():
        raise FileNotFoundError(
            f"Analytics source not found: {ANALYTICS_PATH}; "
            f"warehouse source not found: {WAREHOUSE_DB}"
        )

    connection = sqlite3.connect(WAREHOUSE_DB)
    try:
        row = connection.execute("SELECT MAX(timestamp) FROM dim_time").fetchone()
    finally:
        connection.close()
    if row is None or row[0] is None:
        raise ValueError("Analytics warehouse contains no timestamps")
    return datetime.fromisoformat(row[0])


def as_sql_timestamp(value: datetime) -> str:
    return value.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def query_network_summary(as_of: datetime) -> dict[str, float | int]:
    """Query all summary metrics from the warehouse at or before ``as_of``."""
    if not WAREHOUSE_DB.exists():
        raise FileNotFoundError(f"Warehouse source not found: {WAREHOUSE_DB}")

    timestamp_value = as_sql_timestamp(as_of)
    connection = sqlite3.connect(WAREHOUSE_DB)
    try:
        summary = connection.execute(
            """
            SELECT
                SUM(f.total_activity) AS total_activity,
                COUNT(DISTINCT CASE
                    WHEN f.total_activity > 0 THEN g.grid_id
                END) AS active_grids
            FROM fact_network_activity AS f
            JOIN dim_time AS t ON t.time_key = f.time_key
            JOIN dim_grid AS g ON g.grid_key = f.grid_key
            WHERE t.timestamp <= ?
            """,
            (timestamp_value,),
        ).fetchone()
        peak_hour = connection.execute(
            """
            SELECT t.hour
            FROM fact_network_activity AS f
            JOIN dim_time AS t ON t.time_key = f.time_key
            WHERE t.timestamp <= ?
            GROUP BY t.hour
            ORDER BY SUM(f.total_activity) DESC, t.hour ASC
            LIMIT 1
            """,
            (timestamp_value,),
        ).fetchone()
        top_grid = connection.execute(
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
            (timestamp_value,),
        ).fetchone()
    finally:
        connection.close()

    if summary is None or summary[0] is None or peak_hour is None or top_grid is None:
        raise LookupError(f"No network activity is available through as_of={as_of.isoformat()}")
    return {
        "total_activity": float(summary[0]),
        "active_grids": int(summary[1] or 0),
        "peak_hour": int(peak_hour[0]),
        "top_grid": int(top_grid[0]),
    }
