"""Phase 4 API: pipeline health and grid evidence endpoints."""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from .API1 import WAREHOUSE_DB, get_configured_as_of
except ImportError:
    from API1 import WAREHOUSE_DB, get_configured_as_of


BASE_DIR = Path(__file__).resolve().parents[1]
STATUS_FILE = BASE_DIR / "logs" / "pipeline_status.json"

app = FastAPI(title="Telecom Pipeline Evidence API")


# 2. Include a top-level healthy boolean so a caller can branch on one field, and a reasons list when it is false.
class PipelineStatusResponse(BaseModel):
    healthy: bool
    reasons: list[str] = Field(default_factory=list)
    last_run_id: str
    timestamp: datetime
    task_status: dict[str, str]
    rows_in: int
    rows_rejected: int
    nulls_handled: int
    rows_published: int
    as_of: datetime
    analytics_age_seconds: float
    freshness: str


# 3. Create GET /network/grid/{grid_id}/location. Read dim_grid and return grid_id, centroid latitude and longitude, and a reference to the polygon. Do not return the full Polygon geometry in this endpoint.
class GridLocationResponse(BaseModel):
    grid_id: int
    centroid_latitude: float | None
    centroid_longitude: float | None
    polygon_reference: str | None


class GridNeighboursResponse(BaseModel):
    grid_id: int
    neighbours: list[int]


def _parse_timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def _read_status() -> dict[str, Any]:
    if not STATUS_FILE.exists():
        raise FileNotFoundError(f"Pipeline status source not found: {STATUS_FILE}")
    with STATUS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _status_payload(status: dict[str, Any], as_of: datetime) -> PipelineStatusResponse:
    status_value = str(status.get("status", "UNKNOWN")).upper()
    processed_exists = bool(status.get("processed_exists", True))
    warehouse_exists = bool(status.get("warehouse_exists", WAREHOUSE_DB.exists()))
    healthy = status_value == "SUCCESS" and processed_exists and warehouse_exists
    reasons: list[str] = []
    if status_value != "SUCCESS":
        reasons.append(f"pipeline status is {status_value}")
    if not processed_exists:
        reasons.append("processed analytics output is unavailable")
    if not warehouse_exists:
        reasons.append("warehouse is unavailable")

    task_status = status.get("task_status") or status.get("tasks") or {
        "quality_check": status_value,
    }
    feature_timestamp = _parse_timestamp(status.get("timestamp", datetime.now().isoformat()))
    age_seconds = max(0.0, (datetime.now() - feature_timestamp).total_seconds())
    freshness = "fresh" if age_seconds <= 86400 else "stale"
    return PipelineStatusResponse(
        healthy=healthy,
        reasons=reasons,
        last_run_id=str(status.get("run_id") or status.get("dag_run_id") or f"{status.get('pipeline', 'pipeline')}-{status.get('timestamp', 'unknown')}"),
        timestamp=feature_timestamp,
        task_status={str(key): str(value) for key, value in task_status.items()},
        rows_in=int(status.get("rows_in", 0)),
        rows_rejected=int(status.get("rows_rejected", 0)),
        nulls_handled=int(status.get("nulls_handled", 0)),
        rows_published=int(status.get("rows_published", 0)),
        as_of=as_of,
        analytics_age_seconds=age_seconds,
        freshness=freshness,
    )


# 1. Create GET /pipeline/status. Read the machine-readable status record written by DE7’s quality_check task. Return the last run identifier and timestamp, per-task status, rows in, rows rejected, nulls handled, rows published, the current AS_OF, and a freshness indicator saying how old the analytics layer is.
@app.get("/pipeline/status", response_model=PipelineStatusResponse)
def pipeline_status() -> PipelineStatusResponse:
    try:
        status = _read_status()
        return _status_payload(status, get_configured_as_of())
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Pipeline status source unavailable: {error}") from error


@app.get("/network/grid/{grid_id}/location", response_model=GridLocationResponse)
def grid_location(grid_id: int) -> GridLocationResponse:
    try:
        if grid_id < 1 or grid_id > 10000:
            raise HTTPException(status_code=404, detail=f"Unknown grid_id: {grid_id}")
        if not WAREHOUSE_DB.exists():
            raise FileNotFoundError(f"Warehouse source not found: {WAREHOUSE_DB}")
        connection = sqlite3.connect(WAREHOUSE_DB)
        try:
            row = connection.execute(
                "SELECT grid_id, centroid_latitude, centroid_longitude, geometry_reference FROM dim_grid WHERE grid_id = ?",
                (grid_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Unknown grid_id: {grid_id}")
        return GridLocationResponse(
            grid_id=int(row[0]),
            centroid_latitude=float(row[1]) if row[1] is not None else None,
            centroid_longitude=float(row[2]) if row[2] is not None else None,
            polygon_reference=row[3],
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Grid location source unavailable: {error}") from error


# 4. Optionally add GET /network/grid/{grid_id}/neighbours returning nearby grid IDs by centroid distance — this is what makes “are the surrounding cells also elevated?” answerable at C2.
@app.get("/network/grid/{grid_id}/neighbours", response_model=GridNeighboursResponse)
def grid_neighbours(grid_id: int, limit: int = 8) -> GridNeighboursResponse:
    try:
        if grid_id < 1 or grid_id > 10000:
            raise HTTPException(status_code=404, detail=f"Unknown grid_id: {grid_id}")
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        connection = sqlite3.connect(WAREHOUSE_DB)
        connection.row_factory = sqlite3.Row
        try:
            origin = connection.execute(
                "SELECT grid_id, centroid_latitude, centroid_longitude FROM dim_grid WHERE grid_id = ?",
                (grid_id,),
            ).fetchone()
            if origin is None:
                raise HTTPException(status_code=404, detail=f"Unknown grid_id: {grid_id}")
            if origin[1] is None or origin[2] is None:
                return GridNeighboursResponse(grid_id=grid_id, neighbours=[])
            rows = connection.execute(
                """
                SELECT grid_id, centroid_latitude, centroid_longitude
                FROM dim_grid
                WHERE grid_id != ? AND centroid_latitude IS NOT NULL AND centroid_longitude IS NOT NULL
                """,
                (grid_id,),
            ).fetchall()
        finally:
            connection.close()
        neighbours = sorted(
            rows,
            key=lambda row: math.hypot(row[1] - origin[1], row[2] - origin[2]),
        )[:limit]
        return GridNeighboursResponse(grid_id=grid_id, neighbours=[int(row[0]) for row in neighbours])
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Grid neighbour source unavailable: {error}") from error


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8006)
