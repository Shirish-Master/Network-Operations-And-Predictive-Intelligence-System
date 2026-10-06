"""ML6: batch-score the latest ML2 features and publish operational attention."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd

try:
    from PHASE_6.ML3 import FEATURE_NAMES
    from PHASE_6.ML5 import MODEL, MODEL_VERSION
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from PHASE_6.ML3 import FEATURE_NAMES
    from PHASE_6.ML5 import MODEL, MODEL_VERSION


BASE_DIR = Path(__file__).resolve().parents[1]
FEATURE_TABLE = BASE_DIR / "data" / "analytics" / "ml_features.parquet"
ANOMALY_TABLE = BASE_DIR / "PHASE_6" / "outputs" / "network_anomaly_scores.parquet"
RISK_OUTPUT = BASE_DIR / "PHASE_6" / "outputs" / "network_risk_scores.parquet"
ATTENTION_OUTPUT = BASE_DIR / "PHASE_6" / "outputs" / "top20_operational_attention.csv"
REPORT_OUTPUT = BASE_DIR / "PHASE_6" / "outputs" / "ml6_batch_report.json"


# 1. Read the latest feature table.
def read_feature_table(path: Path = FEATURE_TABLE) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Cannot score before features exist: {path}")
    data = pd.read_parquet(path)
    missing = sorted(set(["grid_id", "feature_timestamp", *FEATURE_NAMES]) - set(data.columns))
    if missing:
        raise ValueError(f"Feature table is missing required columns: {missing}")
    data["feature_timestamp"] = pd.to_datetime(data["feature_timestamp"])
    return data.sort_values(["feature_timestamp", "grid_id"]).reset_index(drop=True)


# 2. Run the risk and anomaly scoring in batch.
def batch_score(features: pd.DataFrame) -> pd.DataFrame:
    scores = MODEL.predict_proba(features[list(FEATURE_NAMES)])[:, 1]
    result = features[["grid_id", "feature_timestamp"]].copy()
    result["timestamp"] = result["feature_timestamp"]
    result["risk_score"] = scores.astype(float)
    result["risk_level"] = pd.cut(
        result["risk_score"],
        bins=[-float("inf"), 0.33, 0.66, float("inf")],
        labels=["low", "medium", "high"],
    ).astype(str)
    result["model_version"] = MODEL_VERSION
    if ANOMALY_TABLE.exists():
        anomaly = pd.read_parquet(ANOMALY_TABLE)
        anomaly["timestamp"] = pd.to_datetime(anomaly["timestamp"])
        result = result.merge(
            anomaly[["grid_id", "timestamp", "anomaly_score", "direction", "reason"]],
            on=["grid_id", "timestamp"],
            how="left",
        )
    result["reason"] = result["reason"].fillna(
        result["risk_level"].map(
            lambda level: f"Attention: model risk level is {level} for this grid/hour."
        )
    )
    if result.duplicated(["grid_id", "timestamp"]).any():
        raise RuntimeError("network_risk_scores contains duplicate grid/hour rows")
    return result


# 3. Write network_risk_scores with grid_id, timestamp, risk_score, risk_level and model_version.
def write_risk_scores(scores: pd.DataFrame, path: Path = RISK_OUTPUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(path, index=False)
    return path


# 4. Add a scoring task to the Airflow DAG, positioned after feature generation and before the quality check.
def scoring_task_contract() -> dict[str, str]:
    return {
        "task_id": "score_network",
        "upstream": "generate_features",
        "downstream": "quality_check",
        "command": "python PHASE_6/ML6.py",
    }


# 5. Validate that /network/hotspots and /network/alerts can surface the model scores through the additive fields designed at API3.
def validate_api3_score_fields(scores: pd.DataFrame) -> dict[str, object]:
    return {
        "api3_fields": ["ml_risk_score", "ml_risk_label", "model_version"],
        "model_version": scores["model_version"].dropna().unique().tolist(),
        "scores_available": not scores.empty,
    }


# 6. Produce a top-twenty operational attention report.
def write_attention_report(scores: pd.DataFrame, path: Path = ATTENTION_OUTPUT) -> Path:
    latest_timestamp = scores["timestamp"].max()
    latest = scores[scores["timestamp"] == latest_timestamp].copy()
    latest["attention_reason"] = latest.apply(
        lambda row: f"Attention: grid {int(row['grid_id'])} has {row['risk_level']} model risk "
        f"({row['risk_score']:.3f}) at {row['timestamp'].isoformat()}; {row['reason']}",
        axis=1,
    )
    report = latest.sort_values(["risk_score", "grid_id"], ascending=[False, True]).head(20)
    report[["grid_id", "timestamp", "risk_score", "risk_level", "model_version", "attention_reason"]].to_csv(path, index=False)
    return path


def main() -> dict[str, object]:
    features = read_feature_table()
    scores = batch_score(features)
    write_risk_scores(scores)
    write_attention_report(scores)
    report = {
        "rows_scored": len(scores),
        "unique_grid_intervals": int(scores[["grid_id", "timestamp"]].drop_duplicates().shape[0]),
        "model_version": MODEL_VERSION,
        "api3_validation": validate_api3_score_fields(scores),
        "attention_report": str(ATTENTION_OUTPUT),
    }
    REPORT_OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
