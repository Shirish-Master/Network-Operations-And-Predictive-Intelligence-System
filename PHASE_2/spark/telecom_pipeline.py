#                    SP7


# This code has created the files saved at: C:\Users\shirish.shyam\Desktop\Shirish_1\data\processed\training_run
# Created files: clean_activity.parquet, hourly_summary.parquet, dashboard_summary.csv

"""Telecom ETL pipeline job contract.

Expected inputs:
- A directory of raw telecom CSV files matching the pattern sms-call-internet-mi-*.csv.
- A GeoJSON reference file containing grid polygons keyed by grid_id / cellId.

Expected outputs:
- clean_activity.parquet: cleaned fact table with one row per grid/hour.
- hourly_summary.parquet: aggregated KPI table with per-grid hourly metrics.
- dashboard_summary.csv: compact daily activity rollup for quick inspection.

Failure conditions:
- Raises a clear error if the input directory does not exist or contains no raw CSV files.
- Raises a clear error if the reference GeoJSON is missing or invalid.
- Raises a clear error if required telecom columns are absent.
- The job exits with status code 1 when startup validation fails.

This module intentionally accepts all runtime paths via command-line arguments so it can
run against the project training folder or any other source location without hardcoded paths.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger("telecom_pipeline")

REQUIRED_INPUT_COLUMNS = {
    "datetime",
    "CellID",
    "countrycode",
    "smsin",
    "smsout",
    "callin",
    "callout",
    "internet",
}

METRIC_COLUMNS = ["sms_in", "sms_out", "call_in", "call_out", "internet_activity"]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for input, output and reference paths."""
    parser = argparse.ArgumentParser(description="Read raw telecom events, clean and aggregate them, then enrich with grid reference data.")
    parser.add_argument("--input-path", type=Path, required=True, help="Directory containing raw telecom CSV files.")
    parser.add_argument("--output-path", type=Path, required=True, help="Directory where the pipeline writes outputs.")
    parser.add_argument("--reference-path", type=Path, required=True, help="GeoJSON file used to enrich grid IDs with geometry metadata.")
    return parser.parse_args()


def read_raw(input_path: Path) -> pd.DataFrame:
    """Read all raw telecom files from an input directory and return one merged DataFrame."""
    logger.info("Starting read_raw for input path: %s", input_path)
    if not input_path.exists() or not input_path.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {input_path}")

    file_paths = sorted(input_path.glob("sms-call-internet-mi-*.csv"))
    if not file_paths:
        raise FileNotFoundError(f"No input files found in {input_path}. Expected files matching 'sms-call-internet-mi-*.csv'.")

    frames = [pd.read_csv(path) for path in file_paths]
    raw = pd.concat(frames, ignore_index=True)
    logger.info("Input rows loaded: %s", len(raw))

    missing_columns = sorted(REQUIRED_INPUT_COLUMNS - set(raw.columns))
    if missing_columns:
        raise ValueError(f"Missing required input columns: {missing_columns}")

    return raw


def clean(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names, coerce values and reject unusable rows."""
    logger.info("Starting clean stage")
    renamed = raw_df.rename(
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

    initial_rows = len(renamed)
    renamed["timestamp"] = pd.to_datetime(renamed["timestamp"], errors="coerce")
    renamed["grid_id"] = pd.to_numeric(renamed["grid_id"], errors="coerce")
    renamed["country_code"] = pd.to_numeric(renamed["country_code"], errors="coerce")

    for column in METRIC_COLUMNS:
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce")

    null_before_fill = int(renamed[METRIC_COLUMNS].isna().sum().sum())
    for column in METRIC_COLUMNS:
        renamed[column] = renamed[column].fillna(0.0)

    invalid_timestamp_count = int(renamed["timestamp"].isna().sum())
    invalid_grid_count = int(renamed["grid_id"].isna().sum())

    cleaned = renamed.dropna(subset=["timestamp", "grid_id"]).copy()
    cleaned = cleaned[["timestamp", "grid_id", "country_code", *METRIC_COLUMNS]].copy()
    cleaned["timestamp"] = cleaned["timestamp"].dt.floor("h")
    cleaned["total_activity"] = cleaned[METRIC_COLUMNS].sum(axis=1)
    cleaned["date"] = cleaned["timestamp"].dt.strftime("%Y-%m-%d")

    rejected_rows = initial_rows - len(cleaned)
    nulls_handled = null_before_fill + invalid_timestamp_count + invalid_grid_count

    logger.info("Rejected rows: %s", rejected_rows)
    logger.info("Nulls handled: %s", nulls_handled)
    logger.info("Cleaned rows: %s", len(cleaned))
    return cleaned


def aggregate(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to one row per hour and grid."""
    logger.info("Starting aggregate stage")
    aggregated = (
        cleaned_df.groupby(["timestamp", "grid_id"], as_index=False)[METRIC_COLUMNS]
        .sum()
    )
    aggregated["total_activity"] = aggregated[METRIC_COLUMNS].sum(axis=1)
    aggregated["date"] = aggregated["timestamp"].dt.strftime("%Y-%m-%d")
    logger.info("Aggregate output rows: %s", len(aggregated))
    return aggregated


def enrich(aggregated_df: pd.DataFrame, reference_path: Path) -> pd.DataFrame:
    """Join grid metrics with the GeoJSON reference so each grid has geometry metadata."""
    logger.info("Starting enrich stage with reference: %s", reference_path)
    if not reference_path.exists():
        raise FileNotFoundError(f"Reference GeoJSON does not exist: {reference_path}")

    with open(reference_path, "r", encoding="utf-8") as file:
        geojson = json.load(file)

    lookup_rows = []
    for feature in geojson.get("features", []) or []:
        properties = feature.get("properties") or {}
        cell_id = properties.get("cellId")
        if cell_id is None:
            continue
        lookup_rows.append({"grid_id": pd.to_numeric(cell_id, errors="coerce"), "geometry": feature.get("geometry")})

    grid_lookup = pd.DataFrame(lookup_rows).dropna(subset=["grid_id"]).drop_duplicates(subset=["grid_id"]).reset_index(drop=True)
    enriched = aggregated_df.merge(grid_lookup, on="grid_id", how="left")

    missing_geometry = int(enriched["geometry"].isna().sum())
    logger.info("Enriched rows: %s", len(enriched))
    logger.info("Missing geometry rows: %s", missing_geometry)
    return enriched


def write_outputs(enriched_df: pd.DataFrame, output_path: Path) -> dict[str, Path]:
    """Persist cleaned, aggregate and dashboard outputs to the requested output directory."""
    logger.info("Starting write_outputs to: %s", output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    clean_path = output_path / "clean_activity.parquet"
    aggregate_path = output_path / "hourly_summary.parquet"
    dashboard_path = output_path / "dashboard_summary.csv"

    clean_table = enriched_df[["timestamp", "grid_id", "date", *METRIC_COLUMNS, "total_activity"]].copy()
    aggregate_table = enriched_df[["timestamp", "date", "grid_id", *METRIC_COLUMNS, "total_activity"]].copy()
    aggregate_table["total_sms_activity"] = aggregate_table["sms_in"] + aggregate_table["sms_out"]
    aggregate_table["total_call_activity"] = aggregate_table["call_in"] + aggregate_table["call_out"]
    aggregate_table["internet_share_of_total_activity"] = (
        aggregate_table["internet_activity"] / aggregate_table["total_activity"].replace(0, pd.NA)
    ).fillna(0.0)

    clean_table.to_parquet(clean_path, index=False)
    aggregate_table.to_parquet(aggregate_path, index=False)

    dashboard = (
        aggregate_table.groupby(["date", "grid_id"], as_index=False)["total_activity"].sum()
        .rename(columns={"total_activity": "daily_activity"})
        .sort_values(["date", "daily_activity"], ascending=[True, False])
        .reset_index(drop=True)
    )
    dashboard.to_csv(dashboard_path, index=False)

    logger.info("Clean activity output: %s", clean_path)
    logger.info("Hourly summary output: %s", aggregate_path)
    logger.info("Dashboard output: %s", dashboard_path)
    logger.info("Output rows written: %s", len(aggregate_table))
    return {
        "clean_activity": clean_path,
        "hourly_summary": aggregate_path,
        "dashboard_summary": dashboard_path,
    }


def main() -> None:
    """Run the full telecom ETL pipeline."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    start_time = datetime.now()
    logger.info("Pipeline start time: %s", start_time)

    args = parse_args()

    try:
        raw_df = read_raw(args.input_path)
        cleaned_df = clean(raw_df)
        aggregated_df = aggregate(cleaned_df)
        enriched_df = enrich(aggregated_df, args.reference_path)
        outputs = write_outputs(enriched_df, args.output_path)
        logger.info("Final status: SUCCESS")
        logger.info("Generated outputs: %s", outputs)
    except Exception as exc:  # pragma: no cover - runtime guard for fail loudly and clearly.
        logger.exception("Final status: FAILED")
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        end_time = datetime.now()
        logger.info("Pipeline end time: %s", end_time)


if __name__ == "__main__":
    main()
