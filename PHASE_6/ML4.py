"""ML4: explainable historical anomaly scores and three-way comparison."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import joblib
import pandas as pd

try:
    from PHASE_1.NP3 import ActivityAlertDetector
    from PHASE_6.ML3 import FEATURE_NAMES, NP3_ALERTS, prepare_training_data, chronological_split
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from PHASE_1.NP3 import ActivityAlertDetector
    from PHASE_6.ML3 import FEATURE_NAMES, NP3_ALERTS, prepare_training_data, chronological_split


BASE_DIR = Path(__file__).resolve().parents[1]
HOURLY_ANALYTICS = BASE_DIR / "data" / "processed" / "hourly_summary.parquet"
ANOMALY_OUTPUT = BASE_DIR / "PHASE_6" / "outputs" / "network_anomaly_scores.parquet"
COMPARISON_OUTPUT = BASE_DIR / "PHASE_6" / "outputs" / "network_three_way_comparison.csv"
REPORT_OUTPUT = BASE_DIR / "PHASE_6" / "outputs" / "ml4_comparison_report.json"
MODEL_OUTPUT = BASE_DIR / "PHASE_6" / "outputs" / "ml3_logistic_regression.joblib"
ANOMALY_THRESHOLD = 0.50


# 1. Compute the historical mean or median per grid and hour-of-day bucket. This is the baseline NP3 could not build from a single day, and it is now possible because the pipeline has accumulated history.
def build_historical_baseline(hourly: pd.DataFrame) -> pd.DataFrame:
    """Reuse NP3's generalized baseline with an hour-of-day bucket."""
    detector = ActivityAlertDetector(hourly)
    return detector.build_baseline(bucket_key="hour_of_day")


# 2. Reuse the NP3 baseline function rather than writing a second one. Generalize it to accept a bucketing key, so the within-day and hour-of-day baselines share one implementation.
def baseline_bucket_counts(baseline_data: pd.DataFrame) -> pd.Series:
    return baseline_data.groupby(["grid_id", "hour_of_day"]).size()


# 3. Compute the deviation from the baseline.
def compute_deviation(baseline_data: pd.DataFrame) -> pd.DataFrame:
    result = baseline_data.copy()
    result["current_value"] = result["total_activity"].astype(float)
    result["deviation"] = result["current_value"] - result["baseline_activity"].astype(float)
    return result


# 4. Define an anomaly score using a simple standardized or percentage deviation.
def score_anomalies(deviation_data: pd.DataFrame, threshold: float = ANOMALY_THRESHOLD) -> pd.DataFrame:
    result = deviation_data.copy()
    baseline = result["baseline_activity"].astype(float)
    result["anomaly_score"] = result["deviation"].abs().div(baseline.where(baseline != 0)).fillna(0.0)
    result["direction"] = result["deviation"].map(lambda value: "high" if value > 0 else "low" if value < 0 else "normal")
    result["anomaly_flag"] = result["anomaly_score"] >= threshold
    result["reason"] = result.apply(
        lambda row: (
            f"Activity is {row['anomaly_score']:.1%} {'above' if row['direction'] == 'high' else 'below'} "
            "the historical grid/hour-of-day median"
            if row["anomaly_flag"]
            else "Activity is within the historical grid/hour-of-day baseline range"
        ),
        axis=1,
    )
    return result[
        [
            "grid_id",
            "timestamp",
            "current_value",
            "baseline_activity",
            "deviation",
            "anomaly_score",
            "direction",
            "anomaly_flag",
            "reason",
        ]
    ].rename(columns={"baseline_activity": "baseline_value"})


# 5. Flag both unusually high and unusually low activity, and keep the direction as a field.
def flagged_anomalies(scored: pd.DataFrame) -> pd.DataFrame:
    return scored[scored["anomaly_flag"] & scored["direction"].isin(["high", "low"])].copy()


# 6. Compare the anomaly flag against the ML3 classifier output and the NP3 rule alerts, and explain the disagreements.
def compare_three_way(anomalies: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    comparison = anomalies.copy()
    comparison["ml3_positive"] = False
    if MODEL_OUTPUT.exists():
        model = joblib.load(MODEL_OUTPUT)
        ml3_data = prepare_training_data()
        _, ml3_test = chronological_split(ml3_data)
        predictions = model.predict(ml3_test[FEATURE_NAMES])
        ml3_keys = {
            (int(row.grid_id), row.feature_timestamp + pd.Timedelta(hours=1))
            for row, prediction in zip(ml3_test.itertuples(), predictions)
            if int(prediction) == 1
        }
        comparison["ml3_positive"] = [
            (int(row.grid_id), pd.Timestamp(row.timestamp)) in ml3_keys
            for row in comparison.itertuples()
        ]

    comparison["np3_alert"] = False
    if NP3_ALERTS.exists():
        alerts = pd.read_csv(NP3_ALERTS, parse_dates=["timestamp"])
        np3_keys = set(zip(alerts["grid_id"].astype(int), alerts["timestamp"]))
        comparison["np3_alert"] = [
            (int(row.grid_id), pd.Timestamp(row.timestamp)) in np3_keys
            for row in comparison.itertuples()
        ]

    comparison["disagreement_reason"] = comparison.apply(
        lambda row: (
            "Anomaly scorer flags a historical hour-of-day deviation while ML3 does not predict the following interval as high activity."
            if row["anomaly_flag"] and not row["ml3_positive"]
            else "NP3 compares within-day behavior, while ML4 compares multiple days at the same hour of day."
            if row["anomaly_flag"] != row["np3_alert"]
            else "Signals agree on this grid/hour."
        ),
        axis=1,
    )
    disagreement = comparison[comparison["disagreement_reason"] != "Signals agree on this grid/hour."]
    report = {
        "rows_compared": len(comparison),
        "anomaly_flags": int(comparison["anomaly_flag"].sum()),
        "ml3_positive": int(comparison["ml3_positive"].sum()),
        "np3_alerts": int(comparison["np3_alert"].sum()),
        "anomaly_ml3_disagreement": int((comparison["anomaly_flag"] != comparison["ml3_positive"]).sum()),
        "anomaly_np3_disagreement": int((comparison["anomaly_flag"] != comparison["np3_alert"]).sum()),
        "example_disagreement": disagreement.iloc[0].to_dict() if not disagreement.empty else None,
    }
    return comparison, report


# 7. Store both the score and a human-readable reason.
def run_ml4() -> dict[str, object]:
    if not HOURLY_ANALYTICS.exists():
        raise FileNotFoundError(f"Hourly analytics not found: {HOURLY_ANALYTICS}")
    hourly = pd.read_parquet(HOURLY_ANALYTICS)
    baseline = build_historical_baseline(hourly)
    bucket_counts = baseline_bucket_counts(baseline)
    scored = score_anomalies(compute_deviation(baseline))
    comparison, comparison_report = compare_three_way(scored)
    ANOMALY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scored.to_parquet(ANOMALY_OUTPUT, index=False)
    comparison.to_csv(COMPARISON_OUTPUT, index=False)
    report = {
        "baseline": "NP3 ActivityAlertDetector.build_baseline(bucket_key='hour_of_day')",
        "bucket_count_minimum": int(bucket_counts.min()),
        "bucket_count_maximum": int(bucket_counts.max()),
        "anomaly_threshold": ANOMALY_THRESHOLD,
        "high_anomalies": int((scored["anomaly_flag"] & (scored["direction"] == "high")).sum()),
        "low_anomalies": int((scored["anomaly_flag"] & (scored["direction"] == "low")).sum()),
        "three_way_comparison": comparison_report,
    }
    REPORT_OUTPUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run_ml4(), indent=2, default=str))
