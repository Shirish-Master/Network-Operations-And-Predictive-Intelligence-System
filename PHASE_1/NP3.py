"""Within-day grid/hour alert detection built on NP2 grid-hour analytics."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd

from PHASE_1.usage_processor import UsageProcessor


LOGGER = logging.getLogger(__name__)


# 1. Start from the grid/hour analytics table produced by aggregate_to_grid_time() in NP2.

class ActivityAlertDetector:
    """Detect unusual hourly activity relative to each grid's own daily pattern."""

    HIGH_MULTIPLIER = 1.5
    DROP_MULTIPLIER = 0.5
    SPIKE_MULTIPLIER = 2.0
    FLOOR_QUANTILE = 0.10

    def __init__(self, grid_hour_data: pd.DataFrame) -> None:
        required = {"grid_id", "timestamp", "total_activity"}
        missing = sorted(required - set(grid_hour_data.columns))
        if missing:
            raise ValueError(f"Missing required grid-hour columns: {missing}")
        self.data = grid_hour_data.copy().sort_values(
            ["grid_id", "timestamp"]
        ).reset_index(drop=True)
        self.activity_floor: Optional[float] = None
        self.alerts = pd.DataFrame()

    # 2. Build the baseline using a configurable bucket key: for each grid_id and bucket, compute the median total_activity excluding the observation being evaluated.

    def build_baseline(self, bucket_key: str = "date") -> pd.DataFrame:
        data = self.data.copy()
        data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
        if data["timestamp"].isna().any():
            raise ValueError("timestamp contains invalid values")
        if (data["total_activity"] < 0).any():
            raise ValueError("total_activity contains negative values")
        data["date"] = data["timestamp"].dt.date
        data["hour_of_day"] = data["timestamp"].dt.hour
        if bucket_key not in {"date", "hour_of_day"}:
            raise ValueError("bucket_key must be 'date' or 'hour_of_day'")

        bucket_totals = data.groupby(["grid_id", bucket_key])["total_activity"].sum()
        positive_totals = bucket_totals[bucket_totals > 0]
        if positive_totals.empty:
            raise ValueError("Cannot derive an activity floor from all-zero data")

        # 3. Apply an activity floor. Grids with very low daily totals produce meaningless ratios and will otherwise dominate the alert list. Choose the floor from the data and document the choice.
        # The 10th percentile suppresses the lowest-volume grid-days while
        # retaining most active grid-days for operational monitoring.
        self.activity_floor = float(positive_totals.quantile(self.FLOOR_QUANTILE))
        data["daily_total_activity"] = data.set_index(["grid_id", bucket_key]).index.map(
            bucket_totals
        )
        data["eligible_grid_day"] = data["daily_total_activity"] >= self.activity_floor
        data["baseline_raw"] = data.groupby(["grid_id", bucket_key])["total_activity"].transform("median")

        data["baseline_activity"] = data["baseline_raw"].clip(lower=self.activity_floor)
        self.data = data
        LOGGER.info(
            "Built leave-one-hour-out median baselines; activity floor=%.4f "
            "(positive grid-day total, %.0fth percentile)",
            self.activity_floor,
            self.FLOOR_QUANTILE * 100,
        )
        return data

    # 4. Define three training rules against that baseline: HIGH_ACTIVITY (current hour materially above the grid's own within-day baseline), ACTIVITY_SPIKE (sharp rise against the immediately preceding hour) and ACTIVITY_DROP (current hour materially below the grid's own baseline).

    def detect_alerts(self) -> pd.DataFrame:
        if "baseline_activity" not in self.data.columns:
            self.build_baseline()
        data = self.data.copy()
        grouped = data.groupby("grid_id", sort=False)
        data["previous_activity"] = grouped["total_activity"].shift(1)
        data["previous_timestamp"] = grouped["timestamp"].shift(1)
        immediate_previous = (
            data["previous_timestamp"].notna()
            & (
                data["timestamp"] - data["previous_timestamp"]
                == pd.Timedelta(hours=1)
            )
        )
        eligible = data["eligible_grid_day"] & data["baseline_activity"].notna()

        # 5. For each grid and hour, compare current activity against the baseline and apply the three rules.
        rules = {
            "HIGH_ACTIVITY": eligible
            & (data["total_activity"] >= self.HIGH_MULTIPLIER * data["baseline_activity"]),
            "ACTIVITY_SPIKE": eligible
            & immediate_previous
            & (data["previous_activity"] > 0)
            & (data["total_activity"] >= self.SPIKE_MULTIPLIER * data["previous_activity"]),
            "ACTIVITY_DROP": eligible
            & (data["total_activity"] <= self.DROP_MULTIPLIER * data["baseline_activity"]),
        }

        # 6. Create alert records containing grid_id, timestamp, alert_type, current_activity, baseline_activity and reason.
        alert_frames = []
        for alert_type, mask in rules.items():
            alert_rows = data.loc[mask, ["grid_id", "timestamp", "total_activity", "baseline_activity"]].copy()
            alert_rows["alert_type"] = alert_type
            if alert_type == "HIGH_ACTIVITY":
                reason = f"Current activity is at least {self.HIGH_MULTIPLIER:.1f}x the leave-one-hour-out baseline"
            elif alert_type == "ACTIVITY_SPIKE":
                reason = f"Current activity is at least {self.SPIKE_MULTIPLIER:.1f}x the immediately preceding hour"
            else:
                reason = f"Current activity is at most {self.DROP_MULTIPLIER:.1f}x the leave-one-hour-out baseline"
            alert_rows["reason"] = reason
            alert_rows.rename(columns={"total_activity": "current_activity"}, inplace=True)
            alert_frames.append(alert_rows)

        columns = [
            "grid_id",
            "timestamp",
            "alert_type",
            "current_activity",
            "baseline_activity",
            "reason",
        ]
        self.alerts = (
            pd.concat(alert_frames, ignore_index=True)[columns]
            if alert_frames
            else pd.DataFrame(columns=columns)
        )
        LOGGER.info("Detected %d alert records", len(self.alerts))
        return self.alerts

    def operational_summary(self) -> Dict[str, object]:
        if self.alerts.empty and "baseline_activity" not in self.data.columns:
            self.detect_alerts()
        grid_hour_count = len(self.data)
        alerts_by_type = self.alerts["alert_type"].value_counts().to_dict()
        top_grids = self.alerts["grid_id"].value_counts().head(10).to_dict()
        return {
            "alerts_by_type": alerts_by_type,
            "top_ten_grids_by_alert_count": top_grids,
            "alerted_grid_hour_proportion": (
                len(self.alerts[["grid_id", "timestamp"]].drop_duplicates())
                / grid_hour_count
                if grid_hour_count
                else 0.0
            ),
            "activity_floor": self.activity_floor,
        }

    # 7. Write alerts to CSV or JSON and print a short operational summary: alerts by type, top ten grids by alert count, and the proportion of all grid/hours that alerted.
    # The default output filename must be network_alerts.csv or network_alerts.json.

    def export_alerts(self, output_path: Union[str, Path] = "PHASE_1/outputs/network_alerts.csv") -> Path:
        if self.alerts.empty and "baseline_activity" not in self.data.columns:
            self.detect_alerts()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            self.alerts.to_json(path, orient="records", date_format="iso", indent=2)
        else:
            self.alerts.to_csv(path, index=False)
        LOGGER.info("Exported %d alert records to %s", len(self.alerts), path)
        return path

    def print_operational_summary(self) -> None:
        summary = self.operational_summary()
        print("Operational summary")
        print(f"Activity floor: {summary['activity_floor']:.4f}")
        print(f"Alerts by type: {summary['alerts_by_type']}")
        print(f"Top ten grids by alert count: {summary['top_ten_grids_by_alert_count']}")
        print(
            "Alerted grid/hour proportion: "
            f"{summary['alerted_grid_hour_proportion']:.2%}"
        )


# 8. Discuss false positives, and write down explicitly what this baseline cannot distinguish.

FALSE_POSITIVE_LIMITATIONS = """
False positives can occur during legitimate events, commuting changes, holidays,
large venues, network maintenance, measurement errors, or sparse observations.
The within-day baseline cannot distinguish a genuine incident from a legitimate
local event, planned maintenance from an outage, a new persistent usage pattern
from an anomaly, or user-driven demand from measurement/data-pipeline problems.
It also does not model spatial relationships, seasonality across multiple days,
or country-code composition because country_code is intentionally excluded from
this grid/hour analytics table.
"""


def run_validation() -> None:
    """Run small unit-style checks for baseline, rules, records, and export."""
    sample = pd.DataFrame(
        {
            "grid_id": [1, 1, 1, 1, 2, 2, 2, 2],
            "timestamp": list(pd.date_range("2013-11-01", periods=4, freq="h")) * 2,
            "total_activity": [10.0, 10.0, 100.0, 10.0, 1.0, 1.0, 1.0, 1.0],
        }
    )
    detector = ActivityAlertDetector(sample)
    baseline = detector.build_baseline()
    assert baseline.loc[2, "baseline_raw"] == 10.0
    alerts = detector.detect_alerts()
    assert {"grid_id", "timestamp", "alert_type", "current_activity", "baseline_activity", "reason"} == set(alerts.columns)
    assert "HIGH_ACTIVITY" in set(alerts["alert_type"])
    assert detector.operational_summary()["alerts_by_type"]["HIGH_ACTIVITY"] >= 1
    output = detector.export_alerts(Path("PHASE_1") / "outputs" / "network_alerts.csv")
    assert output.exists()
    assert "cannot distinguish" in FALSE_POSITIVE_LIMITATIONS
    LOGGER.info("All NP3 validations passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_validation()

    processor = UsageProcessor(
        Path(__file__).resolve().parent.parent
        / "data"
        / "landing"
        / "sms-call-internet-mi-2013-11-01.csv"
    )
    processor.load_data()
    processor.clean_data()
    processor.derive_time_features()
    processor.aggregate_to_grid_time()
    grid_hour = processor.derive_activity_features()

    detector = ActivityAlertDetector(grid_hour)
    detector.build_baseline()
    detector.detect_alerts()
    detector.export_alerts(Path("PHASE_1") / "outputs" / "network_alerts.csv")
    detector.print_operational_summary()
    print(FALSE_POSITIVE_LIMITATIONS.strip())
