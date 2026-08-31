# DE1 Design Document

## 1. Architecture

Daily telecom activity files are ingested from the landing layer, validated and normalized in Spark, and then joined to the static Milano grid reference in `milano-grid.geojson`. The enriched and aggregated outputs are stored in processed and analytics layers, then surfaced through FastAPI to React dashboards and to Claude for interpretation.

```text
CSV source files
   -> landing
   -> raw validation / cleaning in Spark
   -> static reference: milano-grid.geojson
   -> processed outputs
   -> analytics outputs
   -> FastAPI API
   -> React dashboard
   -> Claude interpretation layer
```

## 2. Layer mapping

- Landing: daily `sms-call-internet-mi-*.csv` source files
- Raw: normalized telecom fact tables in CSV or Parquet
- Reference: `milano-grid.geojson` as static geometry lookup, not a daily ingestion file
- Processed: cleaned and intermediate activity tables
- Analytics: `hourly_grid_summary`, `daily_grid_summary`, `hotspots`, alerts, and risk outputs
- Tools: Spark for ETL, SQL for validation and rollups, Airflow for orchestration, FastAPI for serving, React for visualization

## 3. Quality gates

### Before raw acceptance
- Required columns exist
- No missing grid IDs or timestamps
- Datetime values are valid and in range
- Numeric conversion succeeds for telecom measures
- Duplicate records remain below threshold
- Grid IDs are present in the approved reference set

### Before analytics publication
- Row counts reconcile with source totals
- Null and missing-geometry rates are within tolerance
- Hourly and daily rollups are internally balanced
- Hotspot and alert tables pass schema and freshness checks
- Alert thresholds and risk scores are reproducible and reviewed

## 4. Analytics outputs

- `hourly_grid_summary`: per grid-hour activity, totals, and intensity metrics
- `daily_grid_summary`: per grid-day rollups and trend indicators
- `hotspots`: top abnormal cells or windows by activity severity or persistence
- `alert table`: threshold-overrun and operational exception records
- `risk table`: business risk score with confidence, impact, and recommended action

## 5. Responsibilities

- Spark: loads, cleans, normalizes, and aggregates telecom data at scale.
- SQL: validates the data and calculates rollups and reporting views.
- Airflow: schedules and orchestrates the ETL and publishing workflow.
- FastAPI: serves validated datasets and summaries to downstream consumers.
- React: renders dashboards, maps, KPIs, and alert panels for users.
- ML: scores anomaly, hotspot, and risk patterns using historical behavior.
- Claude: interprets analytics results and produces human-readable operational summaries.

## 6. Assumptions and non-goals

### Assumptions
- Daily telecom CSVs are the main source feed.
- The grid geometry is static and shared across all runs.
- Dashboards require both operational and decision-support views.
- Data quality checks must happen before analytics publication.

### Non-goals
- Real-time streaming network ingestion
- Personal customer-level tracking
- Direct network control or autonomous remediation
- Replacing the warehouse or BI stack with a new platform

## Final summary

This design moves daily telecom activity from raw files into cleaned, validated, and enriched analytics outputs, then exposes them to React and Claude while keeping the Milano grid as a static reference rather than a daily source feed.
