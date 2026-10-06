"""Phase 5 React dashboard: grid activity page contract."""

from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
API_BASE_URL = "http://127.0.0.1:8000"


# 1. Create a grid input or search control.
def grid_control() -> str:
    return "grid_id number input with a Search button"


# 2. Call GET /network/grid/{grid_id}.
def grid_endpoint(grid_id: int) -> str:
    return f"{API_BASE_URL}/network/grid/{grid_id}"


# 3. Render an activity table or a simple time-series chart.
def activity_view() -> str:
    return "hourly activity table"


# 4. Display call, SMS, internet and total activity as separate series.
def activity_series() -> tuple[str, ...]:
    return ("call_activity", "sms_activity", "internet_activity", "total_activity")


# 5. Handle an unknown grid gracefully.
def unknown_grid_state() -> str:
    return "display the API error without replacing the rest of the dashboard"


if __name__ == "__main__":
    print(grid_endpoint(5161))
