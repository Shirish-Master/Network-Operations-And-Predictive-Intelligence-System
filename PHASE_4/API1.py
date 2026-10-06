"""Phase 4 API: expose the network summary from curated data layers."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from .API1_service import (
        ANALYTICS_PATH,
        WAREHOUSE_DB,
        as_sql_timestamp,
        get_configured_as_of,
        query_network_summary,
    )
except ImportError:
    from API1_service import (
        ANALYTICS_PATH,
        WAREHOUSE_DB,
        as_sql_timestamp,
        get_configured_as_of,
        query_network_summary,
    )

_as_sql_timestamp = as_sql_timestamp

app = FastAPI(title="Telecom Network API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 4. Use a Pydantic response model.
class NetworkSummaryResponse(BaseModel):
    total_activity: float
    active_grids: int
    peak_hour: int
    top_grid: int
    as_of: datetime


# 1. Create GET /network/summary.
@app.get("/network/summary", response_model=NetworkSummaryResponse)
def network_summary(
    as_of: datetime | None = None,
) -> NetworkSummaryResponse:
    try:
        configured_as_of = get_configured_as_of()
        effective_as_of = as_of or configured_as_of

        # 5. Query the warehouse and analytics layer rather than raw CSV.
        summary = query_network_summary(effective_as_of)

        # 2. Return total_activity, active_grids, peak_hour and top_grid.
        return NetworkSummaryResponse(
            total_activity=summary["total_activity"],
            active_grids=summary["active_grids"],
            peak_hour=summary["peak_hour"],
            top_grid=summary["top_grid"],
            as_of=effective_as_of,
        )
    # 6. Return clear 500 errors when the data source is unavailable, and include the effective as_of in every successful response.
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Network summary data source unavailable: {error}",
        ) from error


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
