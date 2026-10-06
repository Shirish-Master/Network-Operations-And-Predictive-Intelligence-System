"""Phase 5 React dashboard: hotspot, alert, and Milan map page contract."""

from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
API_BASE_URL = "http://127.0.0.1:8000"
REFERENCE_PATH = "/reference/milano-grid.geojson"


# 1. Call /network/hotspots and /network/alerts.
def signal_endpoints() -> tuple[str, str]:
    return (f"{API_BASE_URL}/network/hotspots", f"{API_BASE_URL}/network/alerts")


# 2. Load a read-only static copy of milano-grid.geojson from the frontend public/reference/ area or an equivalent static route. Fetch it once and hold it in state — it must not be re-fetched on every interaction.
def static_reference_path() -> str:
    return REFERENCE_PATH


# 3. Render ranked rows with grid, activity, alert or risk status, and hourly timestamp.
def ranked_signal_fields() -> tuple[str, ...]:
    return ("grid_id", "total_activity", "status", "timestamp")


# 4. Add limit and severity filtering.
def signal_filters() -> tuple[str, ...]:
    return ("limit", "severity")


# 5. Render the Milan grid polygons and join hotspot/alert status to the map by grid_id.
def map_join_key() -> str:
    return "grid_id"


# 6. Visually distinguish NORMAL, ATTENTION and HIGH in both the ranked table and the map.
def signal_statuses() -> tuple[str, ...]:
    return ("NORMAL", "ATTENTION", "HIGH")


# 7. Allow a selected or highlighted polygon to open the Grid Explorer for that grid.
def polygon_action() -> str:
    return "select grid and navigate to Grid Activity"


if __name__ == "__main__":
    print(signal_endpoints())
