# SP7 Job Contract

## Telecommunication pipeline job contract

### Expected inputs
- A directory of raw telecom CSV files matching the pattern `sms-call-internet-mi-*.csv`.
- A GeoJSON reference file containing grid polygons keyed by `grid_id` / `cellId`.

### Expected outputs
- `clean_activity.parquet`: cleaned fact table with one row per grid/hour.
- `hourly_summary.parquet`: aggregated KPI table with per-grid hourly metrics.
- `dashboard_summary.csv`: compact daily activity rollup for quick inspection.

### Failure conditions
- Raises a clear error if the input directory does not exist or contains no raw CSV files.
- Raises a clear error if the reference GeoJSON is missing or invalid.
- Raises a clear error if required telecom columns are absent.
- The job exits with status code 1 when startup validation fails.

### Runtime behavior
- The job reads raw telecom files, validates required columns, cleans invalid or null values, aggregates by timestamp and grid, enriches with GeoJSON geometry, and writes outputs to the requested output directory.
- Logging is included for input rows, rejected rows, nulls handled, output rows, start and end time, and final status.

### Output location contract
- The reusable pipeline accepts paths via command-line arguments and can be run against the project training folder or any similar input set without hardcoded paths.
- Example run:
  - `python telecom_pipeline.py --input-path ... --output-path ... --reference-path ...`

### Files created by the pipeline
- `data/processed/training_run/clean_activity.parquet`
- `data/processed/training_run/hourly_summary.parquet`
- `data/processed/training_run/dashboard_summary.csv`

### Scripts that generate data folder outputs
- `PHASE_2/spark/telecom_pipeline.py` creates the training run under `data/processed/training_run`.
- `PHASE_2/SP6.py` creates the canonical processed and analytics outputs under `data/processed/activity` and `data/analytics/hourly_grid_summary`.
