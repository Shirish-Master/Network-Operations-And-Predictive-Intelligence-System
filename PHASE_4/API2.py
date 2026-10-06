"""Phase 4 API: expose one grid's hourly activity history."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from .API1 import _as_sql_timestamp, get_configured_as_of
    from .API2_service import WAREHOUSE_DB, query_grid_activity, validate_grid_activity_sql
except ImportError:
    from API1 import _as_sql_timestamp, get_configured_as_of
    from API2_service import WAREHOUSE_DB, query_grid_activity, validate_grid_activity_sql


app = FastAPI(title="Telecom Network Grid API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 3. Return the activity time series and the derived measures.
class GridActivityPoint(BaseModel):
    timestamp: datetime
    total_activity: float
    sms_activity: float
    call_activity: float
    internet_activity: float


class GridResponse(BaseModel):
    grid_id: int
    activity: list[GridActivityPoint]
    total_activity: float
    average_hourly_activity: float
    peak_hour: int | None
    active_hours: int
    as_of: datetime


# 1. Create GET /network/grid/{grid_id}.
@app.get("/network/grid/{grid_id}", response_model=GridResponse)
def network_grid(
    grid_id: int,
    date: date | None = None,
    hour: int | None = None,
    as_of: datetime | None = None,
) -> GridResponse:
    try:
        # 2. Add optional date, hour and as_of query parameters. Default the window to the trailing 24 hourly intervals ending at AS_OF.
        if grid_id < 1 or grid_id > 10000:
            raise HTTPException(status_code=404, detail=f"Unknown grid_id: {grid_id}")
        if hour is not None and (hour < 0 or hour > 23):
            raise HTTPException(status_code=422, detail="hour must be between 0 and 23")

        effective_as_of = as_of or get_configured_as_of()
        start_timestamp = _as_sql_timestamp(effective_as_of - timedelta(hours=23))
        end_timestamp = _as_sql_timestamp(effective_as_of)
        if not WAREHOUSE_DB.exists():
            raise FileNotFoundError(f"Warehouse source not found: {WAREHOUSE_DB}")

        connection = sqlite3.connect(WAREHOUSE_DB)
        connection.row_factory = sqlite3.Row
        try:
            known_grid = connection.execute(
                "SELECT 1 FROM dim_grid WHERE grid_id = ?",
                (grid_id,),
            ).fetchone()
            if known_grid is None:
                raise HTTPException(status_code=404, detail=f"Unknown grid_id: {grid_id}")

            rows = query_grid_activity(
                connection,
                grid_id,
                start_timestamp,
                end_timestamp,
                date,
                hour,
            )
            # 5. Validate the results against SQL.
            validate_grid_activity_sql(
                connection,
                grid_id,
                start_timestamp,
                end_timestamp,
                date,
                hour,
                rows,
            )
        finally:
            connection.close()

        activity = [
            GridActivityPoint(
                timestamp=datetime.fromisoformat(row[0]),
                total_activity=float(row[1]),
                sms_activity=float(row[2]),
                call_activity=float(row[3]),
                internet_activity=float(row[4]),
            )
            for row in rows
        ]
        total_activity = sum(point.total_activity for point in activity)
        peak_hour = max(activity, key=lambda point: point.total_activity).timestamp.hour if activity else None

        return GridResponse(
            grid_id=grid_id,
            activity=activity,
            total_activity=total_activity,
            average_hourly_activity=total_activity / len(activity) if activity else 0.0,
            peak_hour=peak_hour,
            active_hours=sum(point.total_activity > 0 for point in activity),
            as_of=effective_as_of,
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Grid activity data source unavailable: {error}",
        ) from error


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
