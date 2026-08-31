#                                                  NP2
# Turning that logic into a reusable data-processing pipeline.

"""Reusable usage-processing pipeline for the Milan telecom activity data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional, Union

import pandas as pd


LOGGER = logging.getLogger(__name__)


# 1. Create a UsageProcessor class that accepts a file path or a DataFrame.

class UsageProcessor:
    """Load, curate, aggregate, profile, and export telecom usage data."""

    COLUMN_MAPPING = {
        "datetime": "timestamp",
        "CellID": "grid_id",
        "countrycode": "country_code",
        "smsin": "sms_in",
        "smsout": "sms_out",
        "callin": "call_in",
        "callout": "call_out",
        "internet": "internet_activity",
    }
    ID_COLUMNS = ["timestamp", "grid_id"]
    ACTIVITY_COLUMNS = [
        "sms_in",
        "sms_out",
        "call_in",
        "call_out",
        "internet_activity",
    ]
    REQUIRED_COLUMNS = ID_COLUMNS + ACTIVITY_COLUMNS

    def __init__(self, source: Union[str, Path, pd.DataFrame]) -> None:
        self.source = source
        self.data: Optional[pd.DataFrame] = None
        self.grid_time_data: Optional[pd.DataFrame] = None
        self.daily_summary: Optional[pd.DataFrame] = None
        self.grid_summary: Optional[pd.DataFrame] = None
        self.kpis: Dict[str, object] = {}

    # 2. Implement load_data(), clean_data(), derive_time_features(), aggregate_to_grid_time(), derive_activity_features(), compute_kpis() and export_summary().

    def load_data(self) -> pd.DataFrame:
        """Load a CSV path or copy an input DataFrame and canonicalize names."""
        if isinstance(self.source, pd.DataFrame):
            data = self.source.copy()
            source_name = "DataFrame"
        else:
            source_path = Path(self.source)
            data = pd.read_csv(source_path)
            source_name = str(source_path)

        data.rename(columns=self.COLUMN_MAPPING, inplace=True)
        # This is a defensive check not in NP1 , if input doesn't contain a column then pipeline won't silently continue.
        missing = sorted(set(self.REQUIRED_COLUMNS) - set(data.columns))
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Data is now stored as processor.data which contain the data frame
        self.data = data
        # Number of rows loadedLOGGER.info("Loaded %s rows from %s", len(data), source_name)
        return data

    def clean_data(self) -> pd.DataFrame:
        """Apply curated-layer null policy and reject invalid activity values."""
        self._require_data()
        data = self.data.copy()
        initial_count = len(data)

        data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
        data["grid_id"] = pd.to_numeric(data["grid_id"], errors="coerce")
        for column in self.ACTIVITY_COLUMNS:
            data[column] = pd.to_numeric(data[column], errors="coerce")

        missing_key = data["timestamp"].isna() | data["grid_id"].isna()
        dropped_count = int(missing_key.sum())
        data = data.loc[~missing_key].copy()

        negative_counts = {
            column: int((data[column] < 0).sum())
            for column in self.ACTIVITY_COLUMNS
        }
        negative_columns = {
            column: count for column, count in negative_counts.items() if count
        }
        if negative_columns:
            raise ValueError(f"Negative activity values found: {negative_columns}")

        data[self.ACTIVITY_COLUMNS] = data[self.ACTIVITY_COLUMNS].fillna(0)
        duplicate_count = int(data.duplicated().sum())
        if duplicate_count:
            data = data.drop_duplicates()
            dropped_count += duplicate_count

        self.data = data
        LOGGER.info(
            "Cleaned rows: loaded=%d, dropped=%d, retained=%d",
            initial_count,
            dropped_count,
            len(data),
        )
        return data

    # 3. Add defensive checks for missing required columns, missing grid_id or timestamp, negative activity values, and the documented curated-layer null handling rule.

    def derive_time_features(self) -> pd.DataFrame:
        """Add calendar fields used by downstream summaries."""
        self._require_data()
        data = self.data.copy()
        data["date"] = data["timestamp"].dt.date
        data["hour"] = data["timestamp"].dt.hour
        data["day_of_week"] = data["timestamp"].dt.day_name()
        self.data = data
        return data

    def aggregate_to_grid_time(self) -> pd.DataFrame:
        """Create one record per grid and hour, without country-code duplication."""
        self._require_data()
        grouped = (
            self.data.groupby(["timestamp", "grid_id"], as_index=False, sort=True)[
                self.ACTIVITY_COLUMNS
            ]
            .sum()
        )
        grouped["date"] = grouped["timestamp"].dt.date
        grouped["hour"] = grouped["timestamp"].dt.hour
        grouped["day_of_week"] = grouped["timestamp"].dt.day_name()
        self.grid_time_data = grouped
        LOGGER.info("Created %d grid-hour records", len(grouped))
        return grouped

    # 4. Add Python logging for load counts, dropped rows and output paths. Use logging, not print.

    def derive_activity_features(self) -> pd.DataFrame:
        """Add total SMS, calls, and activity to the grid-hour table."""
        data = self._require_grid_time_data().copy()
        data["total_sms"] = data["sms_in"] + data["sms_out"]
        data["total_calls"] = data["call_in"] + data["call_out"]
        data["total_activity"] = (
            data["total_sms"] + data["total_calls"] + data["internet_activity"]
        )
        self.grid_time_data = data
        return data

    def compute_kpis(self) -> Dict[str, object]:
        """Build KPI values and daily and grid-level summary tables."""
        data = self._require_grid_time_data()
        self.daily_summary = (
            data.groupby("date", as_index=False)[
                ["total_sms", "total_calls", "internet_activity", "total_activity"]
            ]
            .sum()
        )
        self.grid_summary = (
            data.groupby("grid_id", as_index=False)[
                ["total_sms", "total_calls", "internet_activity", "total_activity"]
            ]
            .sum()
        )
        busiest_hour_row = data.groupby("timestamp")["total_activity"].sum().idxmax()
        busiest_grid_row = data.groupby("grid_id")["total_activity"].sum().idxmax()
        self.kpis = {
            "grid_count": int(data["grid_id"].nunique()),
            "time_start": data["timestamp"].min(),
            "time_end": data["timestamp"].max(),
            "grid_hour_record_count": len(data),
            "busiest_hour": busiest_hour_row,
            "busiest_grid": busiest_grid_row,
        }
        return self.kpis

    # 5. Generate one-record-per-grid/hour analytics data, plus daily and grid-level summary tables. Preserve country_code only in the raw/canonical layer or in a separate optional analysis.

    def export_summary(self, output_dir: Union[str, Path] = "outputs") -> Dict[str, Path]:
        """Export grid-hour, daily, grid, and KPI tables as CSV files."""
        if not self.kpis:
            self.compute_kpis()
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        tables = {
            "grid_hour_usage": self._require_grid_time_data(),
            "daily_summary": self.daily_summary,
            "grid_summary": self.grid_summary,
            "kpis": pd.DataFrame([self.kpis]),
        }
        exported = {}
        for name, table in tables.items():
            if table is None:
                raise RuntimeError(f"Summary table '{name}' was not created")
            path = output_path / f"{name}.csv"
            table.to_csv(path, index=False)
            exported[name] = path
            LOGGER.info("Exported %s rows to %s", len(table), path)
        return exported

    def _require_data(self) -> pd.DataFrame:
        if self.data is None:
            raise RuntimeError("Call load_data() before this method")
        return self.data

    def _require_grid_time_data(self) -> pd.DataFrame:
        if self.grid_time_data is None:
            raise RuntimeError("Call aggregate_to_grid_time() before this method")
        return self.grid_time_data


def run_validation() -> None:
    # 6. Write one small unit-style validation for each major method.
    sample = pd.DataFrame(
        {
            "datetime": ["2013-11-01 00:00:00", "2013-11-01 00:00:00"],
            "CellID": [1, 1],
            "countrycode": [39, 44],
            "smsin": [1.0, None],
            "smsout": [2.0, 1.0],
            "callin": [0.0, 1.0],
            "callout": [1.0, 0.0],
            "internet": [10.0, 5.0],
        }
    )
    processor = UsageProcessor(sample)
    assert len(processor.load_data()) == 2
    assert processor.clean_data()["sms_in"].eq(0).sum() == 1
    assert "hour" in processor.derive_time_features()
    assert len(processor.aggregate_to_grid_time()) == 1
    assert processor.derive_activity_features()["total_activity"].iloc[0] == 21
    assert processor.compute_kpis()["grid_count"] == 1
    exported = processor.export_summary(Path("outputs") / "np2_validation")
    assert all(path.exists() for path in exported.values())
    LOGGER.info("All NP2 method validations passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_validation()
