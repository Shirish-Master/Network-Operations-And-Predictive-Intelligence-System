#Database warehouse is created in data/analytics/warehouse.db
from pathlib import Path
import json
import sqlite3

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

PROCESSED_FILE = BASE_DIR / "data" / "processed" / "hourly_summary.parquet"
REFERENCE_FILE = BASE_DIR / "data" / "reference" / "milano-grid.geojson"

WAREHOUSE_DB = BASE_DIR / "data" / "analytics" / "warehouse.db"

WAREHOUSE_DB.parent.mkdir(parents=True, exist_ok=True)


# 4. Create the SQL tables in PostgreSQL, MySQL or SQLite
# as appropriate to the environment.

def create_tables(conn):

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dim_time (
        time_key INTEGER PRIMARY KEY,
        timestamp TEXT UNIQUE,
        date TEXT,
        year INTEGER,
        month INTEGER,
        day INTEGER,
        hour INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dim_grid (
        grid_key INTEGER PRIMARY KEY,
        grid_id INTEGER UNIQUE,
        centroid_latitude REAL,
        centroid_longitude REAL,
        geometry_reference TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fact_network_activity (
        activity_id INTEGER PRIMARY KEY,
        time_key INTEGER,
        grid_key INTEGER,
        sms_in REAL,
        sms_out REAL,
        call_in REAL,
        call_out REAL,
        internet_activity REAL,
        total_activity REAL,
        total_sms_activity REAL,
        total_call_activity REAL,
        internet_share_of_total_activity REAL,
        FOREIGN KEY(time_key) REFERENCES dim_time(time_key),
        FOREIGN KEY(grid_key) REFERENCES dim_grid(grid_key)
    )
    """)

    conn.commit()


# 5. Load the dimensions and the fact data from the Spark output,
# populating dim_grid once from the static Milan reference rather than
# once per hourly activity record.

def load_dim_time(conn, dataframe):

    time_df = dataframe[["timestamp"]].drop_duplicates().copy()

    time_df["timestamp"] = pd.to_datetime(time_df["timestamp"])

    time_df["date"] = time_df["timestamp"].dt.date.astype(str)
    time_df["year"] = time_df["timestamp"].dt.year
    time_df["month"] = time_df["timestamp"].dt.month
    time_df["day"] = time_df["timestamp"].dt.day
    time_df["hour"] = time_df["timestamp"].dt.hour

    time_df.to_sql(
        "dim_time",
        conn,
        if_exists="append",
        index=False
    )


# 5. Load the dimensions and the fact data from the Spark output,
# populating dim_grid once from the static Milan reference rather than
# once per hourly activity record.

def load_dim_grid(conn):

    with open(REFERENCE_FILE, "r", encoding="utf-8") as file:
        geojson = json.load(file)

    rows = []

    for feature in geojson.get("features", []):

        properties = feature.get("properties", {})

        cell_id = properties.get("cellId")

        if cell_id is None:
            continue

        geometry = feature.get("geometry") or {}
        coordinate_rings = geometry.get("coordinates", [])
        if geometry.get("type") == "Polygon":
            ring = coordinate_rings[0] if coordinate_rings else []
        elif geometry.get("type") == "MultiPolygon":
            ring = coordinate_rings[0][0] if coordinate_rings and coordinate_rings[0] else []
        else:
            ring = []
        longitudes = [point[0] for point in ring if len(point) >= 2]
        latitudes = [point[1] for point in ring if len(point) >= 2]
        rows.append(
            {
                "grid_id": int(cell_id),
                "centroid_latitude": sum(latitudes) / len(latitudes) if latitudes else None,
                "centroid_longitude": sum(longitudes) / len(longitudes) if longitudes else None,
                "geometry_reference": "milano-grid.geojson",
            }
        )

    grid_df = pd.DataFrame(rows).drop_duplicates(subset=["grid_id"])

    existing = pd.read_sql_query(
        "SELECT grid_id FROM dim_grid",
        conn
    )

    if not existing.empty:
        grid_df = grid_df[
            ~grid_df["grid_id"].isin(existing["grid_id"])
        ]

    if not grid_df.empty:
        grid_df.to_sql(
            "dim_grid",
            conn,
            if_exists="append",
            index=False
        )


# 5. Load the dimensions and the fact data from the Spark output,
# populating dim_grid once from the static Milan reference rather than
# once per hourly activity record.

def load_fact_table(conn, dataframe):

    dim_time = pd.read_sql_query(
        "SELECT time_key, timestamp FROM dim_time",
        conn
    )

    dim_grid = pd.read_sql_query(
        "SELECT grid_key, grid_id FROM dim_grid",
        conn
    )

    fact_df = dataframe.copy()

    fact_df["timestamp"] = (
        pd.to_datetime(fact_df["timestamp"])
        .astype(str)
    )

    fact_df = fact_df.merge(
        dim_time,
        on="timestamp",
        how="left"
    )

    fact_df = fact_df.merge(
        dim_grid,
        on="grid_id",
        how="left"
    )

    fact_df = fact_df[
        [
            "time_key",
            "grid_key",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "total_activity",
            "total_sms_activity",
            "total_call_activity",
            "internet_share_of_total_activity",
        ]
    ]

    fact_df.to_sql(
        "fact_network_activity",
        conn,
        if_exists="append",
        index=False
    )


# 7. Add simple indexing on the common filter and join columns.

def create_indexes(conn):

    cursor = conn.cursor()

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_fact_time
    ON fact_network_activity(time_key)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_fact_grid
    ON fact_network_activity(grid_key)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_dim_grid_id
    ON dim_grid(grid_id)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_dim_time_timestamp
    ON dim_time(timestamp)
    """)

    conn.commit()


# 6. Run queries for top grids, hourly trends and internet-heavy windows.

def run_queries(conn):

    print("\nTOP 10 GRIDS\n")

    top_grids = pd.read_sql_query(
        """
        SELECT
            g.grid_id,
            SUM(f.total_activity) AS total_activity
        FROM fact_network_activity f
        JOIN dim_grid g
            ON f.grid_key = g.grid_key
        GROUP BY g.grid_id
        ORDER BY total_activity DESC
        LIMIT 10
        """,
        conn,
    )

    print(top_grids)

    print("\nHOURLY TRENDS\n")

    hourly_trends = pd.read_sql_query(
        """
        SELECT
            t.hour,
            SUM(f.total_activity) AS activity
        FROM fact_network_activity f
        JOIN dim_time t
            ON f.time_key = t.time_key
        GROUP BY t.hour
        ORDER BY t.hour
        """,
        conn,
    )

    print(hourly_trends)

    print("\nINTERNET HEAVY WINDOWS\n")

    internet_windows = pd.read_sql_query(
        """
        SELECT
            t.timestamp,
            g.grid_id,
            f.internet_share_of_total_activity
        FROM fact_network_activity f
        JOIN dim_time t
            ON f.time_key = t.time_key
        JOIN dim_grid g
            ON f.grid_key = g.grid_key
        ORDER BY
            f.internet_share_of_total_activity DESC
        LIMIT 10
        """,
        conn,
    )

    print(internet_windows)


def main():

    if WAREHOUSE_DB.exists():
        WAREHOUSE_DB.unlink()
    #To avoid database duplication
        
    print("Loading Spark output...")

    dataframe = pd.read_parquet(PROCESSED_FILE)

    conn = sqlite3.connect(WAREHOUSE_DB)

    create_tables(conn)
    load_dim_grid(conn)
    load_dim_time(conn, dataframe)
    load_fact_table(conn, dataframe)
    create_indexes(conn)

    run_queries(conn)

    conn.close()

    print("\nWarehouse created successfully:")
    print(WAREHOUSE_DB)


if __name__ == "__main__":
    main()