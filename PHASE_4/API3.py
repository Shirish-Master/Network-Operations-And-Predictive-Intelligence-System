"""Phase 4 API: expose curated hotspots and rule-based network alerts."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from .API1 import WAREHOUSE_DB, _as_sql_timestamp, get_configured_as_of
    from .API3_service import read_risk_scores, read_rule_based_alerts
except ImportError:
    from API1 import WAREHOUSE_DB, _as_sql_timestamp, get_configured_as_of
    from API3_service import read_risk_scores, read_rule_based_alerts


app = FastAPI(title="Telecom Network Signals API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 4. Design the response shape so ML risk fields can be added later without breaking the React client.
class SignalItem(BaseModel):
    grid_id: int
    timestamp: datetime
    total_activity: float
    sms_activity: float
    call_activity: float
    internet_activity: float
    status: str | None = None
    severity: str | None = None
    alert_type: str | None = None
    baseline_activity: float | None = None
    reason: str
    ml_risk_score: float | None = None
    ml_risk_label: str | None = None
    model_version: str | None = None


class SignalResponse(BaseModel):
    items: list[SignalItem]
    as_of: datetime


# 3. Initially serve the rule-based NP3 alerts.


# 1. Create GET /network/hotspots and GET /network/alerts.
@app.get("/network/hotspots", response_model=SignalResponse)
def hotspots(
    limit: int = 10,
    severity: str | None = None,
    as_of: datetime | None = None,
) -> SignalResponse:
    try:
        # 2. Allow limit, severity and as_of query parameters.
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        if severity is not None and severity not in {"low", "medium", "high"}:
            raise HTTPException(status_code=422, detail="severity must be low, medium, or high")

        effective_as_of = as_of or get_configured_as_of()
        risk_scores = read_risk_scores(effective_as_of)
        if not WAREHOUSE_DB.exists():
            raise FileNotFoundError(f"Warehouse source not found: {WAREHOUSE_DB}")

        connection = sqlite3.connect(WAREHOUSE_DB)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT
                    g.grid_id,
                    t.timestamp,
                    f.total_activity,
                    f.total_sms_activity,
                    f.total_call_activity,
                    f.internet_activity
                FROM fact_network_activity AS f
                JOIN dim_time AS t ON t.time_key = f.time_key
                JOIN dim_grid AS g ON g.grid_key = f.grid_key
                WHERE t.timestamp <= ?
                ORDER BY f.total_activity DESC, t.timestamp DESC, g.grid_id ASC, f.activity_id ASC
                LIMIT ?
                """,
                (_as_sql_timestamp(effective_as_of), limit),
            ).fetchall()
        finally:
            connection.close()

        items = [SignalItem.model_validate({
            "grid_id": int(row[0]), "timestamp": datetime.fromisoformat(row[1]),
            "total_activity": float(row[2]), "sms_activity": float(row[3]),
            "call_activity": float(row[4]), "internet_activity": float(row[5]),
            "status": "hotspot", "severity": severity or "high",
            "reason": "Highest recorded hourly total activity through the effective as_of",
            **risk_scores.get((int(row[0]), datetime.fromisoformat(row[1])), {}),
        }) for row in rows]
        return SignalResponse(items=items, as_of=effective_as_of)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Hotspot data source unavailable: {error}",
        ) from error


# 5. Include grid_id, hourly timestamp, the relevant activity measures, status or severity, and a human-readable reason.
@app.get("/network/alerts", response_model=SignalResponse)
def alerts(
    limit: int = 10,
    severity: str | None = None,
    as_of: datetime | None = None,
) -> SignalResponse:
    try:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
        if severity is not None and severity not in {"low", "medium", "high"}:
            raise HTTPException(status_code=422, detail="severity must be low, medium, or high")

        effective_as_of = as_of or get_configured_as_of()
        risk_scores = read_risk_scores(effective_as_of)
        items = [
            SignalItem.model_validate({
                **item.model_dump(),
                **risk_scores.get((item.grid_id, item.timestamp), {}),
            })
            for item in read_rule_based_alerts(effective_as_of, severity)[:limit]
        ]
        return SignalResponse(items=items, as_of=effective_as_of)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Alert data source unavailable: {error}",
        ) from error


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002)
