"""Phase 2, question set 1-11: enrich telecom activity with Milan grid geometries."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ACTIVITY_COLUMNS = ["sms_in", "sms_out", "call_in", "call_out", "internet_activity"]


def read_landing_data(data_folder: Path) -> pd.DataFrame:
    """Read the telecom landing data and normalize the activity schema."""
    file_paths = sorted(data_folder.glob("sms-call-internet-mi-*.csv"))
    if not file_paths:
        raise FileNotFoundError(f"No landing files found in {data_folder}")

    frames = []
    for path in file_paths:
        frames.append(pd.read_csv(path))

    raw = pd.concat(frames, ignore_index=True)
    renamed = raw.rename(
        columns={
            "datetime": "timestamp",
            "CellID": "grid_id",
            "countrycode": "country_code",
            "smsin": "sms_in",
            "smsout": "sms_out",
            "callin": "call_in",
            "callout": "call_out",
            "internet": "internet_activity",
        }
    )
    renamed["timestamp"] = pd.to_datetime(renamed["timestamp"], errors="coerce")
    for column in ["grid_id", "country_code"]:
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce")
    for column in ACTIVITY_COLUMNS:
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce").fillna(0.0)

    activity = renamed[["timestamp", "grid_id", *ACTIVITY_COLUMNS]].copy()
    activity["timestamp"] = activity["timestamp"].dt.floor("h")
    activity = activity.groupby(["timestamp", "grid_id"], as_index=False)[ACTIVITY_COLUMNS].sum()
    activity["total_activity"] = activity[ACTIVITY_COLUMNS].sum(axis=1)
    return activity


def read_geojson(grid_path: Path) -> pd.DataFrame:
    """Load the Milan grid GeoJSON and flatten the features into a grid lookup table."""
    with open(grid_path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    rows = []
    for feature in geo.get("features", []):
        props = feature.get("properties") or {}
        cell_id = props.get("cellId")
        if cell_id is None:
            continue
        rows.append({
            "grid_id": cell_id,
            "geometry": feature.get("geometry"),
        })

    lookup = pd.DataFrame(rows)
    lookup["grid_id"] = pd.to_numeric(lookup["grid_id"], errors="coerce")
    return lookup.dropna(subset=["grid_id"]).reset_index(drop=True)


# Question 1: Load milano-grid.geojson and inspect its structure: the top-level type, where the grid identifier is stored, and the geometry type.
# Implementation

def inspect_geojson_structure(grid_path: Path) -> dict:
    with open(grid_path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    features = geo.get("features", [])
    first_feature = features[0] if features else {}
    return {
        "top_level_type": geo.get("type"),
        "grid_id_field": (first_feature.get("properties") or {}).get("cellId"),
        "geometry_type": (first_feature.get("geometry") or {}).get("type"),
        "feature_count": len(features),
    }


# Question 2: Identify the common key between the telecom activity dataset and the GeoJSON. In the GeoJSON it is properties.cellId; in the project schema it is grid_id.
# Implementation

def identify_join_key() -> dict:
    return {
        "telecom_key": "grid_id",
        "geojson_key": "properties.cellId",
        "join_type": "left join on grid_id",
    }


# Question 3: Normalize the identifier: flatten features[] into a lookup of grid_id + geometry, mapping properties.cellId → grid_id.
# Implementation

def normalize_grid_lookup(grid_path: Path) -> pd.DataFrame:
    with open(grid_path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    rows = []
    for feature in geo.get("features", []):
        props = feature.get("properties") or {}
        cell_id = props.get("cellId")
        if cell_id is None:
            continue
        rows.append({
            "grid_id": cell_id,
            "geometry": feature.get("geometry"),
        })

    lookup = pd.DataFrame(rows)
    lookup["grid_id"] = pd.to_numeric(lookup["grid_id"], errors="coerce")
    return lookup.dropna(subset=["grid_id"]).reset_index(drop=True)


# Question 4: Inspect the size of the grid lookup relative to the activity DataFrame — 10,000 rows against many millions.
# Implementation

def compare_lookup_size(activity_df: pd.DataFrame, grid_lookup: pd.DataFrame) -> dict:
    return {
        "activity_rows": len(activity_df),
        "grid_lookup_rows": len(grid_lookup),
        "lookup_to_activity_ratio": len(grid_lookup) / len(activity_df) if len(activity_df) else 0.0,
    }


# Question 5: Perform a left join between the processed network activity data and the Milan grid lookup on grid_id.
# Implementation

def left_join_activity_to_grid(activity_df: pd.DataFrame, grid_lookup: pd.DataFrame) -> pd.DataFrame:
    activity_df = activity_df.copy()
    grid_lookup = grid_lookup.copy()
    activity_df["grid_id"] = pd.to_numeric(activity_df["grid_id"], errors="coerce")
    enriched = activity_df.merge(
        grid_lookup,
        on="grid_id",
        how="left",
        validate="m:1",
    )
    return enriched


# Question 6: Validate the join by checking the count of distinct activity grids before the join, the count after, the number of grids with missing geometry, and the percentage successfully enriched.
# Implementation

def validate_join(activity_df: pd.DataFrame, enriched_df: pd.DataFrame) -> dict:
    before_grids = activity_df["grid_id"].dropna().nunique()
    after_grids = enriched_df["grid_id"].dropna().nunique()
    missing_geometry = enriched_df["geometry"].isna().sum()
    enriched_count = (enriched_df["geometry"].notna()).sum()
    total_rows = len(enriched_df)
    percentage_successful = (enriched_count / total_rows) * 100 if total_rows else 0.0
    return {
        "distinct_activity_grids_before_join": before_grids,
        "distinct_activity_grids_after_join": after_grids,
        "grids_with_missing_geometry": int(missing_geometry),
        "successful_enrichment_percentage": percentage_successful,
    }


# Question 7: Validate the join geographically as well as numerically — see the acceptance criteria. A coverage percentage alone is not sufficient evidence that the join is correct.
# Implementation

def validate_geo_join(enriched_df: pd.DataFrame) -> dict:
    geom_valid = enriched_df["geometry"].apply(lambda g: isinstance(g, dict) and g.get("type") in {"Polygon", "MultiPolygon"})
    valid_rows = int(geom_valid.sum())
    invalid_rows = int((~geom_valid).sum())
    return {
        "valid_geometry_rows": valid_rows,
        "invalid_geometry_rows": invalid_rows,
        "geometry_validity_rate": (valid_rows / len(enriched_df)) * 100 if len(enriched_df) else 0.0,
    }


# Question 8: Compare the Spark execution plan for a standard join against a broadcast join, and explain why the grid lookup is a broadcast candidate.
# Implementation

def explain_broadcast_join() -> dict:
    return {
        "standard_join": "Spark shuffles both sides by the join key and materializes large intermediate partitions.",
        "broadcast_join": "Spark sends the small GeoJSON lookup table to every executor and keeps it in memory for a local join.",
        "why_broadcast_candidate": "The grid lookup is tiny (~10,000 rows) compared with millions of activity rows, so broadcasting it minimizes shuffle cost and makes the join substantially faster.",
    }


# Question 9: Create an enriched dataset containing timestamp, grid_id, sms_in, sms_out, call_in, call_out, internet_activity, total_activity and geometry.
# Implementation

def create_enriched_dataset(activity_df: pd.DataFrame, grid_lookup: pd.DataFrame) -> pd.DataFrame:
    enriched = activity_df.merge(grid_lookup, on="grid_id", how="left")
    return enriched[
        [
            "timestamp",
            "grid_id",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "total_activity",
            "geometry",
        ]
    ].reset_index(drop=True)


# Question 10: Identify the top high-activity grids for a selected window and retain their geometry for later visualization.
# Implementation

def top_high_activity_grids(enriched_df: pd.DataFrame, window_start: pd.Timestamp, window_end: pd.Timestamp, top_n: int = 10) -> pd.DataFrame:
    window_df = enriched_df[
        (enriched_df["timestamp"] >= window_start) & (enriched_df["timestamp"] <= window_end)
    ].copy()
    top = window_df.groupby("grid_id", as_index=False)["total_activity"].sum().sort_values("total_activity", ascending=False).head(top_n)
    result = top.merge(
        enriched_df[["grid_id", "geometry"]].drop_duplicates(subset=["grid_id"]),
        on="grid_id",
        how="left",
    )
    return result.reset_index(drop=True)


# Question 11: Optionally derive the centroid of each grid polygon, for simpler map visualizations and API responses.
# Implementation

def derive_grid_centroids(enriched_df: pd.DataFrame) -> pd.DataFrame:
    centroid_rows = []
    for _, row in enriched_df.dropna(subset=["geometry"]).iterrows():
        geom = row["geometry"]
        if geom.get("type") == "Polygon":
            coords = geom["coordinates"][0]
            xs = [coord[0] for coord in coords]
            ys = [coord[1] for coord in coords]
            centroid_rows.append({
                "grid_id": row["grid_id"],
                "centroid_lon": sum(xs) / len(xs),
                "centroid_lat": sum(ys) / len(ys),
            })
        elif geom.get("type") == "MultiPolygon":
            coords = geom["coordinates"][0][0]
            xs = [coord[0] for coord in coords]
            ys = [coord[1] for coord in coords]
            centroid_rows.append({
                "grid_id": row["grid_id"],
                "centroid_lon": sum(xs) / len(xs),
                "centroid_lat": sum(ys) / len(ys),
            })

    return pd.DataFrame(centroid_rows)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    data_folder = root / "data" / "landing"
    geojson_path = root / "data" / "reference" / "milano-grid.geojson"

    activity_df = read_landing_data(data_folder)
    grid_lookup = normalize_grid_lookup(geojson_path)

    geo_structure = inspect_geojson_structure(geojson_path)
    join_key_info = identify_join_key()
    size_check = compare_lookup_size(activity_df, grid_lookup)
    enriched_df = left_join_activity_to_grid(activity_df, grid_lookup)
    join_validation = validate_join(activity_df, enriched_df)
    geo_validation = validate_geo_join(enriched_df)
    broadcast_explanation = explain_broadcast_join()
    enriched_dataset = create_enriched_dataset(activity_df, grid_lookup)

    selected_start = pd.Timestamp("2013-11-01 00:00:00")
    selected_end = pd.Timestamp("2013-11-01 23:00:00")
    hotspot_grids = top_high_activity_grids(enriched_dataset, selected_start, selected_end, top_n=10)
    centroids = derive_grid_centroids(enriched_dataset)

    print("GeoJSON structure:", geo_structure)
    print("Join key:", join_key_info)
    print("Lookup vs activity size:", size_check)
    print("Join validation:", join_validation)
    print("Geographic validation:", geo_validation)
    print("Broadcast join rationale:", broadcast_explanation)
    print("Top hotspot grids:")
    print(hotspot_grids.head(10).to_string(index=False))
    print("Centroid preview:")
    print(centroids.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
