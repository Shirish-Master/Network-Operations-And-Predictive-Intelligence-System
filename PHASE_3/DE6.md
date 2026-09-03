# DE6 – Warehouse Modelling for Network Analytics

## Goal

Create an analytics-ready relational model from the processed activity summaries so that operations teams can run repeatable and efficient queries without directly scanning raw files.

---

## 1. Identify the measures and the dimensions present in hourly_grid_summary.

### Dimensions

#### Time Dimension

Represents when the activity occurred.

Attributes:

```text
timestamp
date
hour
day
month
year
```

#### Grid Dimension

Represents the telecom grid where activity occurred.

Attributes:

```text
grid_id
centroid_latitude
centroid_longitude
geometry_reference
```

---

### Measures

Measures represent the numeric activity values stored in the warehouse.

```text
sms_in
sms_out
call_in
call_out
internet_activity
total_activity
total_sms_activity
total_call_activity
internet_share_of_total_activity
```

---

## 2. Design fact_network_activity with grid and time keys and the activity measures.

### Fact Table: fact_network_activity

```text
fact_network_activity
```

Purpose:

```text
Stores measurable telecom network activity at the grid and time level.
```

Structure:

```text
fact_network_activity
------------------------------------------------------
activity_id
time_key
grid_key
sms_in
sms_out
call_in
call_out
internet_activity
total_activity
total_sms_activity
total_call_activity
internet_share_of_total_activity
```

### Relationships

```text
fact_network_activity
        |
        +---- time_key  -> dim_time
        |
        +---- grid_key  -> dim_grid
```

---

## 3. Design dim_time and dim_grid. dim_grid holds grid_id plus optional centroid latitude and longitude and a geometry reference. Do not repeat the full Polygon geometry in fact_network_activity.

### Dimension: dim_time

Purpose:

```text
Stores reusable time-related attributes.
```

Structure:

```text
dim_time
--------------------------------
time_key
timestamp
date
year
month
day
hour
```

---

### Dimension: dim_grid

Purpose:

```text
Stores grid metadata once and avoids duplication within the fact table.
```

Structure:

```text
dim_grid
--------------------------------
grid_key
grid_id
centroid_latitude
centroid_longitude
geometry_reference
```

### Design Decision

The full GeoJSON polygon must not be duplicated inside:

```text
fact_network_activity
```

Reason:

```text
Repeating geometry for every activity record increases storage,
creates redundancy, and slows analytical queries.
```

Instead:

```text
The geometry is stored once in dim_grid and referenced through grid_key.
```

---

## 4. Create the SQL tables in PostgreSQL, MySQL or SQLite as appropriate to the environment.

### Database Choice

```text
SQLite
```

Reason:

```text
SQLite requires no server installation,
works within the training VM,
and can run identically in local environments.
```

### SQL Definition

#### dim_time

```sql
CREATE TABLE dim_time (
    time_key INTEGER PRIMARY KEY,
    timestamp TEXT,
    date TEXT,
    year INTEGER,
    month INTEGER,
    day INTEGER,
    hour INTEGER
);
```

#### dim_grid

```sql
CREATE TABLE dim_grid (
    grid_key INTEGER PRIMARY KEY,
    grid_id INTEGER UNIQUE,
    centroid_latitude REAL,
    centroid_longitude REAL,
    geometry_reference TEXT
);
```

#### fact_network_activity

```sql
CREATE TABLE fact_network_activity (
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
);
```

---

## 5. Load the dimensions and the fact data from the Spark output, populating dim_grid once from the static Milan reference rather than once per hourly activity record.

### Data Sources

#### Fact Source

```text
data/processed/hourly_summary.parquet
```

#### Grid Reference Source

```text
data/reference/milano-grid.geojson
```

---

### Loading Strategy

#### dim_grid

```text
Load once from milano-grid.geojson.
```

Contains:

```text
grid_id
centroid_latitude
centroid_longitude
geometry_reference
```

#### dim_time

```text
Created from unique timestamps found in hourly_summary.parquet.
```

Contains:

```text
date
year
month
day
hour
```

#### fact_network_activity

```text
Loaded from hourly_summary.parquet.
```

References:

```text
time_key
grid_key
```

instead of storing duplicate dimensional information.

---

## 6. Run queries for top grids, hourly trends and internet-heavy windows.

### Top Grids by Total Activity

```sql
SELECT
    g.grid_id,
    SUM(f.total_activity) AS total_activity
FROM fact_network_activity f
JOIN dim_grid g
    ON f.grid_key = g.grid_key
GROUP BY g.grid_id
ORDER BY total_activity DESC
LIMIT 10;
```

---

### Hourly Trends

```sql
SELECT
    t.hour,
    SUM(f.total_activity) AS activity
FROM fact_network_activity f
JOIN dim_time t
    ON f.time_key = t.time_key
GROUP BY t.hour
ORDER BY t.hour;
```

---

### Internet-Heavy Windows

```sql
SELECT
    t.timestamp,
    g.grid_id,
    f.internet_share_of_total_activity
FROM fact_network_activity f
JOIN dim_time t
    ON f.time_key = t.time_key
JOIN dim_grid g
    ON f.grid_key = g.grid_key
ORDER BY f.internet_share_of_total_activity DESC
LIMIT 10;
```

---

## 7. Add simple indexing on the common filter and join columns.

### Index on Time Key

```sql
CREATE INDEX idx_fact_time
ON fact_network_activity(time_key);
```

### Index on Grid Key

```sql
CREATE INDEX idx_fact_grid
ON fact_network_activity(grid_key);
```

### Index on Grid ID

```sql
CREATE INDEX idx_dim_grid_id
ON dim_grid(grid_id);
```

### Index on Timestamp

```sql
CREATE INDEX idx_dim_time_timestamp
ON dim_time(timestamp);
```

---

# Warehouse Model Diagram

```text
                    dim_time
               ------------------
               time_key (PK)
               timestamp
               date
               year
               month
               day
               hour
                      |
                      |
                      |
                      v

fact_network_activity ----------------> dim_grid
---------------------------------       -------------------
activity_id (PK)                        grid_key (PK)
time_key (FK)                           grid_id
grid_key (FK)                           centroid_latitude
sms_in                                  centroid_longitude
sms_out                                 geometry_reference
call_in
call_out
internet_activity
total_activity
total_sms_activity
total_call_activity
internet_share_of_total_activity
```

---

# Expected Outputs

## Star Schema

```text
fact_network_activity
dim_time
dim_grid
```

## Warehouse Queries

```text
Top Grids Query
Hourly Trends Query
Internet-Heavy Windows Query
```

## Indexed Warehouse Tables

```text
Indexed fact and dimension tables for efficient filtering and joins.
```
