"""Prepare the GeoPandas-backed Milan grid layer for the React map."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE = BASE_DIR / "data" / "reference" / "milano-grid.geojson"
OUTPUT = BASE_DIR / "PHASE_5" / "frontend" / "public" / "reference" / "milano-grid-web.geojson"


def prepare_map_layer() -> Path:
    grid = gpd.read_file(SOURCE)
    if "cellId" not in grid.columns:
        raise ValueError("Milan grid reference must contain cellId")
    grid = grid[["cellId", "geometry"]].rename(columns={"cellId": "grid_id"})
    grid["grid_id"] = grid["grid_id"].astype(int)
    grid = grid[grid.geometry.notna() & ~grid.geometry.is_empty].copy()
    grid = grid.to_crs("EPSG:4326")
    grid["geometry"] = grid.geometry.simplify(tolerance=0.00001, preserve_topology=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    grid.to_file(OUTPUT, driver="GeoJSON")
    return OUTPUT


if __name__ == "__main__":
    output = prepare_map_layer()
    print(f"Prepared {output}")
