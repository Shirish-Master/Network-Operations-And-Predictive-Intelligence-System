"""Phase 5 React dashboard: network risk prediction page contract."""

from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
RISK_API_BASE_URL = "http://127.0.0.1:8004"
RISK_ENDPOINT = "/network/predict-risk"


# 1. Submit feature values or a selected grid to POST /network/predict-risk.
def risk_prediction_request() -> str:
    return f"{RISK_API_BASE_URL}{RISK_ENDPOINT}"


# 2. Display the risk score, the risk level and the model version.
def risk_result_fields() -> tuple[str, ...]:
    return ("risk_score", "risk_level", "model_version")


# 3. Show the model output visually separate from any narrative explanation.
def output_sections() -> tuple[str, ...]:
    return ("model output", "explanation note")


# 4. Add a placeholder “Explain with AI” action for the later Claude phase.
def explain_with_ai_action() -> str:
    return "placeholder action for the later Claude phase"


if __name__ == "__main__":
    print(risk_prediction_request())
