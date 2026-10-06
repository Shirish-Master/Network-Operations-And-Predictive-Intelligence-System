"""Service layer for hotspot and rule-based alert signals."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parents[1]
ALERTS_FILE = BASE_DIR / "PHASE_1" / "outputs" / "network_alerts.csv"
RISK_SCORES_FILE = BASE_DIR / "PHASE_6" / "outputs" / "network_risk_scores.parquet"
_RISK_SCORE_CACHE: pd.DataFrame | None = None


class SignalRecord(BaseModel):
    grid_id: int
    timestamp: datetime
    total_activity: float
    sms_activity: float
    call_activity: float
    internet_activity: float
    status: str | None = None
    severity: str | None = None
    alert_type: str | None = None
    baseline_activity: float | None = None
    reason: str
    ml_risk_score: float | None = None
    ml_risk_label: str | None = None
    model_version: str | None = None


def severity_for_alert(alert_type: str) -> str:
    return "high" if alert_type in {"HIGH_ACTIVITY", "ACTIVITY_SPIKE"} else "medium"


def read_rule_based_alerts(as_of: datetime, severity: str | None) -> list[SignalRecord]:
    if not ALERTS_FILE.exists():
        raise FileNotFoundError(f"NP3 alert source not found: {ALERTS_FILE}")

    items: list[SignalRecord] = []
    with ALERTS_FILE.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            timestamp = datetime.fromisoformat(row["timestamp"])
            alert_severity = severity_for_alert(row["alert_type"])
            if timestamp > as_of or (severity is not None and alert_severity != severity):
                continue
            current_activity = float(row["current_activity"])
            items.append(
                SignalRecord(
                    grid_id=int(row["grid_id"]),
                    timestamp=timestamp,
                    total_activity=current_activity,
                    sms_activity=0.0,
                    call_activity=0.0,
                    internet_activity=0.0,
                    status="alert",
                    severity=alert_severity,
                    alert_type=row["alert_type"],
                    baseline_activity=float(row["baseline_activity"]),
                    reason=row["reason"],
                )
            )
    return sorted(items, key=lambda item: (item.timestamp, item.grid_id, item.alert_type or ""), reverse=True)


def read_risk_scores(as_of: datetime) -> dict[tuple[int, datetime], dict[str, object]]:
    """Read additive ML6 scores without changing the rule-based signal source."""
    global _RISK_SCORE_CACHE
    if not RISK_SCORES_FILE.exists():
        return {}
    if _RISK_SCORE_CACHE is None:
        _RISK_SCORE_CACHE = pd.read_parquet(RISK_SCORES_FILE)
        _RISK_SCORE_CACHE["timestamp"] = pd.to_datetime(_RISK_SCORE_CACHE["timestamp"])
    scores = _RISK_SCORE_CACHE
    scores = scores[scores["timestamp"] <= pd.Timestamp(as_of)]
    return {
        (int(row.grid_id), row.timestamp.to_pydatetime()): {
            "ml_risk_score": float(row.risk_score),
            "ml_risk_label": str(row.risk_level),
            "model_version": str(row.model_version),
        }
        for row in scores.itertuples()
    }
