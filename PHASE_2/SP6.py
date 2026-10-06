# This code has created the files saved at: C:\Users\shirish.shyam\Desktop\Shirish_1\data\processed and C:\Users\shirish.shyam\Desktop\Shirish_1\data\analytics
# Created files: data/processed/activity, data/analytics/hourly_grid_summary, PHASE_2/dashboard_summary.csv

"""Phase 2, question set 1-6: write processed parquet outputs and validate the persisted analytics assets."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds

ACTIVITY_COLUMNS = ["sms_in", "sms_out", "call_in", "call_out", "internet_activity"]


def read_landing_data(data_folder: Path) -> pd.DataFrame:
    """Read and normalize the raw telecom activity data."""
    file_paths = sorted(data_folder.glob("sms-call-internet-mi-*.csv"))
    if not file_paths:
        raise FileNotFoundError(f"No landing files found in {data_folder}")

    frames = []
    for path in file_paths:
        frames.append(pd.read_csv(path))

    raw = pd.concat(frames, ignore_index=True)
    renamed = raw.rename(
        columns={
            "datetime": "timestamp",
            "CellID": "grid_id",
            "countrycode": "country_code",
            "smsin": "sms_in",
            "smsout": "sms_out",
            "callin": "call_in",
            "callout": "call_out",
            "internet": "internet_activity",
        }
    )
    renamed["timestamp"] = pd.to_datetime(renamed["timestamp"], errors="coerce")
    for column in ["grid_id", "country_code"]:
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce")
    for column in ACTIVITY_COLUMNS:
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce").fillna(0.0)

    activity = renamed[["timestamp", "grid_id", *ACTIVITY_COLUMNS]].copy()
    activity["timestamp"] = activity["timestamp"].dt.floor("h")
    activity = activity.groupby(["timestamp", "grid_id"], as_index=False)[ACTIVITY_COLUMNS].sum()
    activity["total_activity"] = activity[ACTIVITY_COLUMNS].sum(axis=1)
    activity["date"] = activity["timestamp"].dt.strftime("%Y-%m-%d")
    return activity


def load_grid_lookup(grid_path: Path) -> pd.DataFrame:
    """Load the Milan grid GeoJSON to a lightweight lookup table."""
    with open(grid_path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    rows = []
    for feature in geo.get("features", []):
        props = feature.get("properties") or {}
        cell_id = props.get("cellId")
        if cell_id is None:
            continue
        rows.append({
            "grid_id": cell_id,
            "geometry": feature.get("geometry"),
        })

    lookup = pd.DataFrame(rows)
    lookup["grid_id"] = pd.to_numeric(lookup["grid_id"], errors="coerce")
    return lookup.dropna(subset=["grid_id"]).reset_index(drop=True)


def build_hourly_grid_summary(activity_df: pd.DataFrame) -> pd.DataFrame:
    """Create the canonical hourly grid summary without duplicating polygon geometry."""
    hourly = activity_df.copy()
    hourly["total_sms_activity"] = hourly["sms_in"] + hourly["sms_out"]
    hourly["total_call_activity"] = hourly["call_in"] + hourly["call_out"]
    hourly["internet_share_of_total_activity"] = (
        hourly["internet_activity"] / hourly["total_activity"].replace(0, pd.NA)
    ).fillna(0.0)

    return hourly[
        [
            "timestamp",
            "date",
            "grid_id",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "total_sms_activity",
            "total_call_activity",
            "total_activity",
            "internet_share_of_total_activity",
        ]
    ].sort_values(["timestamp", "grid_id"]).reset_index(drop=True)


def build_dashboard_summary(hourly_summary: pd.DataFrame) -> pd.DataFrame:
    """Build a compact dashboard summary for quick inspection."""
    daily = hourly_summary.groupby(["date", "grid_id"], as_index=False)["total_activity"].sum()
    daily = daily.rename(columns={"total_activity": "daily_activity"})
    daily = daily.sort_values(["date", "daily_activity"], ascending=[True, False]).reset_index(drop=True)
    return daily


# Question 1: Write the clean activity data as Parquet.
# Implementation

def write_clean_activity_parquet(activity_df: pd.DataFrame, output_dir: Path) -> Path:
    clean_dir = output_dir / "activity"
    clean_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(activity_df, preserve_index=False)
    ds.write_dataset(
        table,
        str(clean_dir),
        format="parquet",
        partitioning=["date"],
        existing_data_behavior="delete_matching",
    )
    return clean_dir


# Question 2: Partition the cleaned output by date.
# Implementation

def write_partitioned_activity_parquet(activity_df: pd.DataFrame, output_dir: Path) -> Path:
    partition_dir = output_dir / "activity"
    partition_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(activity_df, preserve_index=False)
    ds.write_dataset(
        table,
        str(partition_dir),
        format="parquet",
        partitioning=["date"],
        existing_data_behavior="delete_matching",
    )
    return partition_dir


# Question 3: Write hourly_grid_summary as Parquet at one record per grid and hour. Keep full Polygon geometry in the static grid reference rather than duplicating it into every analytics record.
# Implementation

def write_hourly_summary_parquet(hourly_summary: pd.DataFrame, output_dir: Path) -> Path:
    summary_dir = output_dir / "hourly_grid_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(hourly_summary, preserve_index=False)
    ds.write_dataset(
        table,
        str(summary_dir),
        format="parquet",
        existing_data_behavior="delete_matching",
    )
    return summary_dir


# Question 4: Write a small dashboard summary as CSV for easy inspection, and retain milano-grid.geojson separately under data/reference/ for map rendering.
# Implementation

def write_dashboard_and_reference(dashboard_summary: pd.DataFrame, phase2_dir: Path, reference_dir: Path, geojson_path: Path, dashboard_filename: str = "dashboard_summary.csv") -> Path:
    phase2_dir.mkdir(parents=True, exist_ok=True)
    dashboard_path = phase2_dir / dashboard_filename
    dashboard_summary.to_csv(dashboard_path, index=False)
    reference_dir.mkdir(parents=True, exist_ok=True)
    reference_path = reference_dir / geojson_path.name
    reference_path.write_text(geojson_path.read_text(encoding="utf-8"), encoding="utf-8")
    return dashboard_path


# Question 5: Read the Parquet output back and validate schema and counts.
# Implementation

def validate_parquet_outputs(activity_df: pd.DataFrame, hourly_summary: pd.DataFrame, output_dir: Path, analytics_dir: Path) -> dict:
    clean_path = output_dir / "activity"
    summary_path = analytics_dir / "hourly_grid_summary"

    clean_table = ds.dataset(str(clean_path), format="parquet")
    summary_table = ds.dataset(str(summary_path), format="parquet")
    clean_read = clean_table.to_table().to_pandas()
    summary_read = summary_table.to_table().to_pandas()

    return {
        "clean_activity_rows": len(clean_read),
        "clean_activity_columns": list(clean_read.columns),
        "hourly_summary_rows": len(summary_read),
        "hourly_summary_columns": list(summary_read.columns),
        "count_match_activity": len(clean_read) == len(activity_df),
        "count_match_hourly": len(summary_read) == len(hourly_summary),
    }


# Question 6: Compare file sizes and explain the benefits of columnar storage.
# Implementation

def compare_file_sizes(output_dir: Path, analytics_dir: Path, dashboard_path: Path) -> dict:
    activity_dir = output_dir / "activity"
    summary_dir = analytics_dir / "hourly_grid_summary"

    def folder_size(path: Path) -> int:
        return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())

    return {
        "activity_folder_size_bytes": folder_size(activity_dir),
        "summary_folder_size_bytes": folder_size(summary_dir),
        "dashboard_csv_size_bytes": dashboard_path.stat().st_size,
        "benefit": "Columnar formats store data by column, compress it efficiently, and read only required fields, which is especially effective for large telecom fact tables.",
    }


def flatten_stale_analytics_folder(analytics_dir: Path) -> None:
    """Remove a stale nested analytics/analytics directory and keep a single canonical analytics root."""
    nested_dir = analytics_dir / "analytics"
    if not nested_dir.exists() or not nested_dir.is_dir():
        return

    for child in nested_dir.iterdir():
        target = analytics_dir / child.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(child), str(target))

    nested_dir.rmdir()


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    phase2_dir = Path(__file__).resolve().parent
    data_folder = root / "data" / "landing"
    output_dir = root / "data" / "processed"
    analytics_dir = root / "data" / "analytics"
    reference_dir = root / "data" / "reference"
    geojson_path = reference_dir / "milano-grid.geojson"

    analytics_dir.mkdir(parents=True, exist_ok=True)
    flatten_stale_analytics_folder(analytics_dir)

    activity_df = read_landing_data(data_folder)
    hourly_summary = build_hourly_grid_summary(activity_df)
    dashboard_summary = build_dashboard_summary(hourly_summary)

    clean_activity_dir = write_clean_activity_parquet(activity_df, output_dir)
    write_partitioned_activity_parquet(activity_df, output_dir)
    summary_dir = write_hourly_summary_parquet(hourly_summary, analytics_dir)
    dashboard_path = write_dashboard_and_reference(dashboard_summary, phase2_dir, reference_dir, geojson_path)

    validation = validate_parquet_outputs(activity_df, hourly_summary, output_dir, analytics_dir)
    size_summary = compare_file_sizes(output_dir, analytics_dir, dashboard_path)

    print("Clean activity path:", clean_activity_dir)
    print("Hourly summary path:", summary_dir)
    print("Dashboard summary path:", dashboard_path)
    print("Validation:", validation)
    print("File-size comparison:", size_summary)


if __name__ == "__main__":
    main()
