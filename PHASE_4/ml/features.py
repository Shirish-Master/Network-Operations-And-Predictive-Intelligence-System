"""Build the leakage-safe ML2 feature table from canonical hourly analytics."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
HOURLY_ANALYTICS = BASE_DIR / "data" / "processed" / "hourly_summary.parquet"
FEATURE_OUTPUT = BASE_DIR / "data" / "analytics" / "ml_features.parquet"
RECENT_WINDOW_HOURS = 24
BASELINE_WINDOW_HOURS = 24
FEATURE_COLUMNS = [
    "grid_id",
    "avg_activity",
    "activity_growth",
    "active_hours",
    "peak_ratio",
    "variability",
    "internet_share",
    "feature_timestamp",
    "data_quality_status",
]


# 1. Fix the feature window convention first: every feature for a prediction at t+1 is computed from the trailing window ending at `t`, inclusive of t and nothing after it. Write this down before writing code.
FEATURE_WINDOW_RULE = "For a prediction at t+1, every feature reads only timestamps from the trailing window ending at t, inclusive."


# 2. Create avg_activity over the recent trailing window.
# 3. Create activity_growth — the recent window against a prior baseline window.
# 4. Create active_hours — the count of hours in the window with activity above zero.
# 5. Create peak_ratio = peak ÷ average over the window.
# 6. Create variability using standard deviation or a coefficient-of-variation style proxy.
# 7. Create internet_share = internet_activity ÷ total_activity.
def build_feature_row(grid_data: pd.DataFrame, feature_timestamp: pd.Timestamp) -> dict[str, object]:
    """Build one row using recent and baseline windows ending no later than t."""
    recent_start = feature_timestamp - pd.Timedelta(hours=RECENT_WINDOW_HOURS - 1)
    baseline_start = feature_timestamp - pd.Timedelta(
        hours=RECENT_WINDOW_HOURS + BASELINE_WINDOW_HOURS - 1
    )
    recent = grid_data[
        (grid_data["timestamp"] >= recent_start)
        & (grid_data["timestamp"] <= feature_timestamp)
    ]
    baseline = grid_data[
        (grid_data["timestamp"] >= baseline_start)
        & (grid_data["timestamp"] < recent_start)
    ]
    if len(recent) != RECENT_WINDOW_HOURS or len(baseline) != BASELINE_WINDOW_HOURS:
        raise ValueError(f"Insufficient hourly history to build features at {feature_timestamp}")

    recent_activity = recent["total_activity"].astype(float)
    baseline_activity = baseline["total_activity"].astype(float)
    recent_average = float(recent_activity.mean())
    baseline_average = float(baseline_activity.mean())
    recent_total = float(recent_activity.sum())
    return {
        "avg_activity": recent_average,
        "activity_growth": (recent_average - baseline_average) / baseline_average if baseline_average else 0.0,
        "active_hours": int((recent_activity > 0).sum()),
        "peak_ratio": float(recent_activity.max() / recent_average) if recent_average else 0.0,
        "variability": float(recent_activity.std(ddof=0) / recent_average) if recent_average else 0.0,
        "internet_share": float(recent["internet_activity"].sum() / recent_total) if recent_total else 0.0,
        "feature_timestamp": feature_timestamp,
        "data_quality_status": "valid",
    }


def build_features(hourly: pd.DataFrame) -> pd.DataFrame:
    """Create one eligible ML2 feature row per grid and feature timestamp."""
    required = {"timestamp", "grid_id", "total_activity", "internet_activity"}
    missing = sorted(required - set(hourly.columns))
    if missing:
        raise ValueError(f"Hourly analytics is missing columns: {missing}")

    data = hourly.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="raise")
    data = data.sort_values(["grid_id", "timestamp"]).drop_duplicates(["grid_id", "timestamp"])
    grouped = data.groupby("grid_id", sort=False)
    activity = data["total_activity"].astype(float)
    internet = data["internet_activity"].astype(float)
    recent_mean = grouped["total_activity"].transform(lambda values: values.rolling(RECENT_WINDOW_HOURS, min_periods=RECENT_WINDOW_HOURS).mean())
    baseline_mean = grouped["total_activity"].transform(lambda values: values.shift(RECENT_WINDOW_HOURS).rolling(BASELINE_WINDOW_HOURS, min_periods=BASELINE_WINDOW_HOURS).mean())
    active_hours = grouped["total_activity"].transform(lambda values: values.gt(0).rolling(RECENT_WINDOW_HOURS, min_periods=RECENT_WINDOW_HOURS).sum())
    peak = grouped["total_activity"].transform(lambda values: values.rolling(RECENT_WINDOW_HOURS, min_periods=RECENT_WINDOW_HOURS).max())
    variability = grouped["total_activity"].transform(lambda values: values.rolling(RECENT_WINDOW_HOURS, min_periods=RECENT_WINDOW_HOURS).std(ddof=0))
    recent_total = grouped["total_activity"].transform(lambda values: values.rolling(RECENT_WINDOW_HOURS, min_periods=RECENT_WINDOW_HOURS).sum())
    recent_internet = grouped["internet_activity"].transform(lambda values: values.rolling(RECENT_WINDOW_HOURS, min_periods=RECENT_WINDOW_HOURS).sum())
    eligible = recent_mean.notna() & baseline_mean.notna()
    result = pd.DataFrame(
        {
            "grid_id": data["grid_id"].astype(int),
            "avg_activity": recent_mean,
            "activity_growth": (recent_mean - baseline_mean).div(baseline_mean.where(baseline_mean != 0)).fillna(0.0),
            "active_hours": active_hours.fillna(0).astype(int),
            "peak_ratio": peak.div(recent_mean.where(recent_mean != 0)).fillna(0.0),
            "variability": variability.div(recent_mean.where(recent_mean != 0)).fillna(0.0),
            "internet_share": recent_internet.div(recent_total.where(recent_total != 0)).fillna(0.0),
            "feature_timestamp": data["timestamp"],
            "data_quality_status": "valid",
        }
    )
    result = result.loc[eligible].reset_index(drop=True)
    return result[FEATURE_COLUMNS]


# 8. Persist the feature table with grid_id and feature_timestamp, where feature_timestamp is t — the last interval the features are allowed to see.
def write_features(output_path: Path = FEATURE_OUTPUT) -> Path:
    if not HOURLY_ANALYTICS.exists():
        raise FileNotFoundError(f"Hourly analytics source not found: {HOURLY_ANALYTICS}")
    features = build_features(pd.read_parquet(HOURLY_ANALYTICS))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(output_path, index=False)
    return output_path


if __name__ == "__main__":
    print(f"Wrote ML2 features to {write_features()}")
