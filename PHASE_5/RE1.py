"""Phase 5 React dashboard setup and API integration contract."""

from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
API_BASE_URL = "http://127.0.0.1:8000"


# 1. Create the app and the API base configuration.
def frontend_configuration() -> dict[str, str]:
    return {
        "frontend_dir": str(FRONTEND_DIR),
        "api_base_url": API_BASE_URL,
    }


# 2. Configure CORS on FastAPI.
def cors_origins() -> tuple[str, ...]:
    return ("http://localhost:5173", "http://127.0.0.1:5173")


# 3. Fetch /network/summary on load.
def summary_endpoint() -> str:
    return "/network/summary"


# 4. Implement loading, success and error states.
def dashboard_states() -> tuple[str, ...]:
    return ("loading", "success", "error")


# 5. Create simple navigation between the dashboard pages.
def dashboard_pages() -> tuple[str, ...]:
    return ("Overview", "Grid Activity", "Alerts")


if __name__ == "__main__":
    print(frontend_configuration())