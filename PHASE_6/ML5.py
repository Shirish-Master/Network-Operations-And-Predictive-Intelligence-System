"""ML5 model service for the real risk prediction endpoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "PHASE_6" / "outputs" / "ml3_logistic_regression.joblib"
MODEL_VERSION = "ml3-logistic-regression-v1"
FEATURE_NAMES = (
    "avg_activity",
    "activity_growth",
    "active_hours",
    "peak_ratio",
    "variability",
    "internet_share",
)


# 1. Load the trained model safely at service startup, with a clear failure if the artifact is missing.
def load_model(model_path: Path = MODEL_PATH) -> Any:
    if not model_path.exists():
        raise RuntimeError(f"Risk model artifact is missing: {model_path}")
    try:
        return joblib.load(model_path)
    except Exception as error:
        raise RuntimeError(f"Risk model artifact could not be loaded: {model_path}: {error}") from error


MODEL = load_model()


# 2. Validate the incoming features against the ML2 schema.
def validate_features(features: dict[str, Any]) -> pd.DataFrame:
    missing = [name for name in FEATURE_NAMES if name not in features]
    if missing:
        raise ValueError(f"Missing ML2 features: {missing}")
    values = {name: float(features[name]) for name in FEATURE_NAMES}
    return pd.DataFrame([values], columns=FEATURE_NAMES)


# 3. Return risk_score, risk_level, model_version and feature_timestamp.
def predict(features: dict[str, Any]) -> dict[str, Any]:
    frame = validate_features(features)
    score = float(MODEL.predict_proba(frame)[0, 1])
    if score >= 0.66:
        risk_level = "high"
    elif score >= 0.33:
        risk_level = "medium"
    else:
        risk_level = "low"
    return {
        "risk_score": score,
        "risk_level": risk_level,
        "model_version": MODEL_VERSION,
        "feature_timestamp": features["feature_timestamp"],
        "contributing_features": top_contributing_features(frame),
    }


# 4. Optionally return the top contributing feature names when the model supports it.
def top_contributing_features(frame: pd.DataFrame, limit: int = 3) -> list[str]:
    classifier = getattr(MODEL, "named_steps", {}).get("classifier")
    scaler = getattr(MODEL, "named_steps", {}).get("scale")
    if classifier is None or not hasattr(classifier, "coef_"):
        return []
    transformed = scaler.transform(frame) if scaler is not None else frame.to_numpy()
    contributions = np.abs(transformed[0] * classifier.coef_[0])
    ranking = np.argsort(contributions)[::-1][:limit]
    return [FEATURE_NAMES[index] for index in ranking]


# 5. Retest the React prediction page without changing the frontend contract.
def model_contract() -> tuple[str, ...]:
    return (
        "risk_score",
        "risk_level",
        "model_version",
        "explanation_note",
        "feature_timestamp",
    )
