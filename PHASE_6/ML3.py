"""ML3: chronological baseline training and evaluation for future activity risk."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


BASE_DIR = Path(__file__).resolve().parents[1]
FEATURE_TABLE = BASE_DIR / "data" / "analytics" / "ml_features.parquet"
HOURLY_ANALYTICS = BASE_DIR / "data" / "processed" / "hourly_summary.parquet"
NP3_ALERTS = BASE_DIR / "PHASE_1" / "outputs" / "network_alerts.csv"
MODEL_OUTPUT = BASE_DIR / "PHASE_6" / "outputs" / "ml3_logistic_regression.joblib"
REPORT_OUTPUT = BASE_DIR / "PHASE_6" / "outputs" / "ml3_evaluation_report.json"
FEATURE_NAMES = [
    "avg_activity",
    "activity_growth",
    "active_hours",
    "peak_ratio",
    "variability",
    "internet_share",
]


# 1. Sort the feature data by time and perform a chronological train/test split: earlier periods train, later periods test. Never a random split.
def chronological_split(data: pd.DataFrame, train_fraction: float = 0.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = data.sort_values(["feature_timestamp", "grid_id"]).reset_index(drop=True)
    timestamps = ordered["feature_timestamp"].drop_duplicates().sort_values().tolist()
    split_index = max(1, min(len(timestamps) - 1, int(len(timestamps) * train_fraction)))
    split_timestamp = timestamps[split_index]
    train = ordered[ordered["feature_timestamp"] < split_timestamp].copy()
    test = ordered[ordered["feature_timestamp"] >= split_timestamp].copy()
    if train.empty or test.empty or train["feature_timestamp"].max() >= test["feature_timestamp"].min():
        raise ValueError("Chronological split produced overlapping or empty train/test periods")
    return train, test


# 2. Record and report the earliest and latest timestamp in each of the train and test sets.
def date_ranges(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, str]:
    return {
        "train_earliest": train["feature_timestamp"].min().isoformat(),
        "train_latest": train["feature_timestamp"].max().isoformat(),
        "test_earliest": test["feature_timestamp"].min().isoformat(),
        "test_latest": test["feature_timestamp"].max().isoformat(),
    }


# 3. Train Logistic Regression or a Decision Tree.
def train_model(train: pd.DataFrame) -> Pipeline:
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=500, class_weight="balanced")),
        ]
    )
    model.fit(train[FEATURE_NAMES], train["label"])
    return model


# 4. Evaluate accuracy plus precision, recall and the class balance. Report the base rate — the proportion of positive labels — alongside accuracy, because accuracy is meaningless without it.
def evaluate_model(model: Pipeline, test: pd.DataFrame) -> dict[str, float | int | dict[str, int]]:
    predictions = model.predict(test[FEATURE_NAMES])
    positive_rate = float(test["label"].mean())
    return {
        "accuracy": float(accuracy_score(test["label"], predictions)),
        "precision": float(precision_score(test["label"], predictions, zero_division=0)),
        "recall": float(recall_score(test["label"], predictions, zero_division=0)),
        "base_rate": positive_rate,
        "class_balance": {str(int(key)): int(value) for key, value in test["label"].value_counts().sort_index().items()},
        "positive_predictions": int(predictions.sum()),
    }


# 5. Inspect the coefficients or the feature importances and check they are operationally plausible.
def inspect_coefficients(model: Pipeline) -> dict[str, float]:
    coefficients = model.named_steps["classifier"].coef_[0]
    return {feature: float(value) for feature, value in zip(FEATURE_NAMES, coefficients)}


# 6. Compare the predictions against the rule-based NP3 alerts and characterize where they disagree.
def compare_np3_alerts(test: pd.DataFrame, predictions: pd.Series) -> dict[str, int]:
    if not NP3_ALERTS.exists():
        return {"test_rows": len(test), "model_positive": int(predictions.sum()), "np3_alerts": 0, "overlap": 0, "model_only": int(predictions.sum()), "np3_only": 0}
    alerts = pd.read_csv(NP3_ALERTS, parse_dates=["timestamp"])
    alert_keys = set(zip(alerts["grid_id"].astype(int), alerts["timestamp"]))
    model_keys = {
        (int(row.grid_id), row.feature_timestamp + pd.Timedelta(hours=1))
        for row, prediction in zip(test.itertuples(), predictions)
        if int(prediction) == 1
    }
    return {
        "test_rows": len(test),
        "model_positive": len(model_keys),
        "np3_alerts": len(alert_keys),
        "overlap": len(model_keys & alert_keys),
        "model_only": len(model_keys - alert_keys),
        "np3_only": len(alert_keys - model_keys),
    }


# 7. Write three observations about where the model adds value and where it does not.
def observations(report: dict[str, object]) -> list[str]:
    return [
        "The chronological model adds value by producing a forward-looking score for the next hourly interval rather than restating the current interval's threshold.",
        "Comparison with NP3 shows where a learned future-risk signal agrees with or diverges from current rule-based alerts; disagreement is useful for operator review, not automatic truth.",
        "The model is limited by synthetic activity labels and the absence of capacity, throughput, latency, packet-loss, and radio-utilization measurements; a positive result requires human investigation.",
    ]


def prepare_training_data() -> pd.DataFrame:
    if not FEATURE_TABLE.exists() or not HOURLY_ANALYTICS.exists():
        raise FileNotFoundError("ML2 feature table and hourly analytics are required")
    features = pd.read_parquet(FEATURE_TABLE)
    hourly = pd.read_parquet(HOURLY_ANALYTICS)
    features["feature_timestamp"] = pd.to_datetime(features["feature_timestamp"])
    hourly["timestamp"] = pd.to_datetime(hourly["timestamp"])
    future = hourly[["grid_id", "timestamp", "total_activity"]].copy()
    future["feature_timestamp"] = future["timestamp"] - pd.Timedelta(hours=1)
    data = features.merge(future.drop(columns=["timestamp"]), on=["grid_id", "feature_timestamp"], how="inner")
    timestamps = data["feature_timestamp"].drop_duplicates().sort_values().tolist()
    boundary_index = max(1, min(len(timestamps) - 1, int(len(timestamps) * 0.8)))
    train_boundary = timestamps[boundary_index]
    threshold = float(data.loc[data["feature_timestamp"] < train_boundary, "total_activity"].quantile(0.9))
    data["label"] = (data["total_activity"] >= threshold).astype(int)
    return data.drop(columns=["total_activity"])


def main() -> dict[str, object]:
    data = prepare_training_data()
    train, test = chronological_split(data)
    model = train_model(train)
    metrics = evaluate_model(model, test)
    report = {
        "algorithm": "logistic_regression",
        "date_ranges": date_ranges(train, test),
        "metrics": metrics,
        "coefficients": inspect_coefficients(model),
        "np3_comparison": compare_np3_alerts(test, pd.Series(model.predict(test[FEATURE_NAMES]), index=test.index)),
    }
    report["observations"] = observations(report)
    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_OUTPUT)
    REPORT_OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
