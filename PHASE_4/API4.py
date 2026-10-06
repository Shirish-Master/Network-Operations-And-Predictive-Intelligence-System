"""Phase 4 API: expose the stable ML2 grid feature contract."""

from __future__ import annotations

import csv
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.dataset as ds
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from .API1 import WAREHOUSE_DB, get_configured_as_of
except ImportError:
    from API1 import WAREHOUSE_DB, get_configured_as_of


BASE_DIR = Path(__file__).resolve().parents[1]
FEATURE_TABLE = Path(
    os.getenv("TELECOM_FEATURE_TABLE", str(BASE_DIR / "data" / "analytics" / "ml_features.parquet"))
)
FEATURE_TABLE_CANDIDATES = (
    FEATURE_TABLE,
    BASE_DIR / "data" / "analytics" / "features.parquet",
    BASE_DIR / "data" / "analytics" / "grid_features.parquet",
    BASE_DIR / "data" / "analytics" / "features.csv",
)
REQUIRED_FEATURES = (
    "avg_activity",
    "activity_growth",
    "active_hours",
    "peak_ratio",
    "variability",
    "internet_share",
    "feature_timestamp",
)

app = FastAPI(title="Telecom ML Features API")


# 3. Define a stable Pydantic schema — this contract is consumed by ML5, RE5 and the Claude tools, and changing it later breaks three consumers.
class GridFeatureResponse(BaseModel):
    grid_id: int
    avg_activity: float
    activity_growth: float
    active_hours: int
    peak_ratio: float
    variability: float
    internet_share: float
    feature_timestamp: datetime
    data_quality_status: str
    feature_freshness: str


def _find_feature_table() -> Path:
    for path in FEATURE_TABLE_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Stored ML2 feature table not found; checked: "
        + ", ".join(str(path) for path in FEATURE_TABLE_CANDIDATES)
    )


def _read_feature_row(grid_id: int) -> dict[str, Any]:
    feature_table = _find_feature_table()
    if feature_table.suffix.lower() == ".csv":
        with feature_table.open("r", encoding="utf-8", newline="") as file:
            rows = csv.DictReader(file)
            for row in rows:
                if int(row["grid_id"]) == grid_id:
                    return dict(row)
        raise LookupError(f"No stored features found for grid_id={grid_id}")

    if feature_table.suffix.lower() == ".db":
        connection = sqlite3.connect(feature_table)
        try:
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            for (table_name,) in tables:
                columns = {
                    row[1]
                    for row in connection.execute(f'PRAGMA table_info("{table_name}")')
                }
                if set(REQUIRED_FEATURES).issubset(columns) and "grid_id" in columns:
                    row = connection.execute(
                        f'SELECT * FROM "{table_name}" WHERE grid_id = ? LIMIT 1',
                        (grid_id,),
                    ).fetchone()
                    if row is not None:
                        names = [item[1] for item in connection.execute(f'PRAGMA table_info("{table_name}")')]
                        return dict(zip(names, row))
        finally:
            connection.close()
        raise LookupError(f"No stored features found for grid_id={grid_id}")

    table = ds.dataset(str(feature_table), format="parquet")
    available = set(table.schema.names)
    missing = set(("grid_id", *REQUIRED_FEATURES)) - available
    if missing:
        raise ValueError(f"Stored feature table is missing columns: {sorted(missing)}")
    columns = ["grid_id", *REQUIRED_FEATURES]
    if "data_quality_status" in available:
        columns.append("data_quality_status")
    filtered = table.to_table(
        columns=columns,
        filter=ds.field("grid_id") == grid_id,
    )
    if filtered.num_rows == 0:
        raise LookupError(f"No stored features found for grid_id={grid_id}")
    records = [
        {key: values[index] for key, values in filtered.to_pydict().items()}
        for index in range(filtered.num_rows)
    ]
    return max(records, key=lambda record: _normalise_timestamp(record["feature_timestamp"]))


def _normalise_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


# 5. Test the response against the stored feature table values.
def _validate_response_against_stored(row: dict[str, Any], response: GridFeatureResponse) -> None:
    for field in REQUIRED_FEATURES:
        expected = _normalise_timestamp(row[field]) if field == "feature_timestamp" else float(row[field])
        actual = getattr(response, field)
        if field == "feature_timestamp":
            matches = actual == expected
        else:
            matches = abs(float(actual) - expected) <= 1e-9
        if not matches:
            raise RuntimeError(f"Response value for {field} failed stored feature table validation")


# 1. Create GET /network/grid/{grid_id}/features.
@app.get("/network/grid/{grid_id}/features", response_model=GridFeatureResponse)
def grid_features(grid_id: int) -> GridFeatureResponse:
    try:
        if grid_id < 1 or grid_id > 10000:
            raise HTTPException(status_code=404, detail=f"Unknown grid_id: {grid_id}")

        # 2. Return the exact ML2 feature set: avg_activity, activity_growth, active_hours, peak_ratio, variability, internet_share, plus feature_timestamp.
        row = _read_feature_row(grid_id)
        response = GridFeatureResponse(
            grid_id=grid_id,
            avg_activity=float(row["avg_activity"]),
            activity_growth=float(row["activity_growth"]),
            active_hours=int(row["active_hours"]),
            peak_ratio=float(row["peak_ratio"]),
            variability=float(row["variability"]),
            internet_share=float(row["internet_share"]),
            feature_timestamp=_normalise_timestamp(row["feature_timestamp"]),
            data_quality_status=str(row.get("data_quality_status", "unknown")),
            feature_freshness="current" if _normalise_timestamp(row["feature_timestamp"]) >= get_configured_as_of() else "stale",
        )

        # 4. Return data-quality status and feature freshness alongside the values.
        _validate_response_against_stored(row, response)
        return response
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Stored ML2 feature source unavailable or invalid: {error}",
        ) from error

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8003)
