"""Phase 5 React dashboard: network summary page contract."""

from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
API_BASE_URL = "http://127.0.0.1:8000"
SUMMARY_PATH = "/network/summary"
METRIC_CARD_COUNT = 4
REPORTING_TIMESTAMP_FIELD = "as_of"


# 1. Call /network/summary.
def summary_request() -> str:
    return f"{API_BASE_URL}{SUMMARY_PATH}"


# 2. Display four metric cards.
def metric_card_fields() -> tuple[str, ...]:
    return ("total_activity", "active_grids", "peak_hour", "top_grid")


# 3. Show the as_of value returned by the API as the reporting timestamp — do not display the browser clock, which would be misleading on a historical dataset.
def reporting_timestamp_field() -> str:
    return REPORTING_TIMESTAMP_FIELD


# 4. Show a small status banner when the API is unavailable.
def unavailable_banner_state() -> str:
    return "error"


# 5. Keep the styling intentionally simple.
def stylesheet_path() -> Path:
    return FRONTEND_DIR / "src" / "styles.css"


if __name__ == "__main__":
    print(summary_request())
