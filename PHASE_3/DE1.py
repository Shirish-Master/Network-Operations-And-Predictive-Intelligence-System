"""DE1.py

Questions 1 to 6:
1. Draw the architecture from the daily activity CSV source plus the static milano-grid.geojson reference through to the React and Claude consumers.
2. Map the landing, raw, reference, processed and analytics layers to file formats and tools. Treat milano-grid.geojson as static reference data, not a daily ingestion file.
3. Identify the quality gates that must pass before raw acceptance and before analytics publication.
4. Define the analytics outputs: hourly_grid_summary, daily_grid_summary, hotspots, and the alert and risk tables.
5. Define the responsibilities of Spark, SQL, Airflow, FastAPI, React, ML and Claude — one sentence each, with no overlap.
6. Produce a one-page design document with explicit assumptions and non-goals.
"""

from __future__ import annotations


def main() -> None:
    print("PHASE_3 / DE1")
    print("========================================")
    print("1. Architecture overview")
    print("- Daily telecom CSVs land in data/landing")
    print("- Spark reads raw files and validates schema, nulls, duplicates, and grid coverage")
    print("- Static reference file data/reference/milano-grid.geojson is loaded as lookup/reference geometry")
    print("- Processed datasets are written to data/processed")
    print("- Analytics tables are written to data/analytics")
    print("- FastAPI exposes curated datasets and summaries to downstream consumers")
    print("- React dashboard consumes API endpoints for maps, KPIs, hotspots, and alerts")
    print("- Claude consumes the validated analytics outputs and narrative summaries for interpretation")
    print()

    print("2. Layer-to-format mapping")
    print("- Landing layer: daily CSV activity files (.csv), ingested as source feeds")
    print("- Raw layer: normalized telecom fact tables (.csv / parquet), handled by Spark and SQL")
    print("- Reference layer: milano-grid.geojson (.geojson), static geometry lookup, not a daily ingestion source")
    print("- Processed layer: cleaned activity and intermediate tables (.parquet, .csv)")
    print("- Analytics layer: hourly_grid_summary, daily_grid_summary, hotspots, alerts, risk tables (.parquet, .csv)")
    print("- Tools: Spark for ETL, SQL for validation and rollups, Airflow for orchestration, FastAPI for API serving")
    print()

    print("3. Quality gates")
    print("- Before raw acceptance: required columns present, no missing core keys, valid datetime ranges, numeric coercion succeeds, duplicate rows below threshold, grid IDs match known reference set")
    print("- Before analytics publication: output row counts reconcile with source input, null rates within tolerance, no missing geometry for active grids, hourly and daily rollups balance, hotspot and alert tables pass freshness and schema checks")
    print()

    print("4. Analytics outputs")
    print("- hourly_grid_summary: one row per grid per hour with sms, call, internet, and total activity")
    print("- daily_grid_summary: one row per grid per day with aggregated activity, intensity, and trend signals")
    print("- hotspots: top stressed cells or grid windows ranked by abnormal activity, persistence, or spikes")
    print("- alert table: exceptions, threshold breaches, outage-risk flags, and business-level notifications")
    print("- risk table: risk score, confidence, impact, and recommended action for each critical grid/time window")
    print()

    print("5. Role split")
    print("- Spark: loads, cleans, normalizes, and aggregates the telecom data at scale.")
    print("- SQL: validates data quality, computes rollups, and exposes reproducible reporting queries.")
    print("- Airflow: schedules, monitors, and orchestrates end-to-end ETL and publication workflows.")
    print("- FastAPI: serves validated datasets and summaries to internal applications and dashboards.")
    print("- React: renders the dashboard, maps, KPIs, hotspot views, and alert cards for users.")
    print("- ML: scores anomaly, risk, and hotspot patterns using historical and live telecom behavior.")
    print("- Claude: interprets analytics output and produces concise operational summaries for human decision-making.")
    print()

    print("6. One-page design document")
    print("Assumptions:")
    print("- Telecom activity is delivered daily as CSV files with a stable schema.")
    print("- A fixed Milano grid reference exists and is reused across all runs.")
    print("- Data freshness is critical for ops teams and dashboard accuracy.")
    print("- The system needs both human-readable summaries and machine-readable analytics tables.")
    print()
    print("Non-goals:")
    print("- Real-time streaming ingestion from live network events.")
    print("- Full customer-level behavior tracking or personal data processing.")
    print("- Building a new ML platform or replacing the company’s warehouse and BI stack.")
    print("- Real-time autonomous remediation; the system supports alerting and decision support, not direct network control.")
    print()

    print("Summary:")
    print("The design moves daily telecom activity from source CSVs into validated, aggregated, and enriched analytics layers, then exposes those outputs to React dashboards and Claude-driven interpretation while keeping the Milano grid reference as a stable static geometry source.")


if __name__ == "__main__":
    main()
