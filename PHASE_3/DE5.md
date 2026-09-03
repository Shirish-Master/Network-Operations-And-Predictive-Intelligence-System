# DE5 – Storage Design and Data Lake Zones

## 1. Map the zones: landing = incoming daily CSVs; raw = immutable accepted CSVs; reference = milano-grid.geojson; processed = Parquet; analytics = warehouse tables and curated Parquet; logs/ = audit and run history.

### Storage Zone Mapping

| Zone | Purpose | Contents |
|--------|----------|----------|
| landing | Temporary arrival location for new datasets | Incoming daily telecom CSV files |
| raw | Immutable storage for accepted source data | Accepted CSV files copied from landing |
| reference | Static reference assets | milano-grid.geojson |
| processed | Cleaned and transformed datasets | clean_activity.parquet, hourly_summary.parquet |
| analytics | Curated analytical outputs | dashboard_summary.csv, warehouse-ready tables, curated Parquet datasets |
| logs | Operational monitoring and audit trail | ingestion_metadata.csv, Airflow logs, pipeline run history |

---

## 2. Define a date-partitioned processed directory structure, and a non-partitioned static location for the reference data.

### Processed Layer Directory Structure

```text
data/
└── processed/
    ├── year=2026/
    │   ├── month=09/
    │   │   ├── day=01/
    │   │   │   ├── clean_activity.parquet
    │   │   │   └── hourly_summary.parquet
```

### Analytics Layer Directory Structure

```text
data/
└── analytics/
    ├── year=2026/
    │   ├── month=09/
    │   │   ├── day=01/
    │   │   │   └── dashboard_summary.csv
```

### Reference Layer Structure

Reference data is static and does not require partitioning.

```text
data/
└── reference/
    └── milano-grid.geojson
```

---

## 3. Explain why raw is retained unchanged.

The raw layer stores accepted source files exactly as they were received.

Reasons for retaining raw data unchanged:

- Preserves the original source record.
- Supports audit and compliance requirements.
- Enables troubleshooting and root-cause analysis.
- Allows pipeline reprocessing when business logic changes.
- Provides a reliable recovery point if downstream processing fails.
- Prevents accidental loss of original information.

The raw layer therefore acts as the system's immutable source of truth.

---

## 4. Compare append and overwrite semantics for each layer.

### Landing Layer

**Append**
- New incoming files are added each day.

**Overwrite**
- Not recommended because incoming files may be lost.

### Raw Layer

**Append**
- Accepted files are continuously added.

**Overwrite**
- Not recommended because raw history must remain immutable.

### Reference Layer

**Append**
- Rarely used.

**Overwrite**
- Allowed when an updated reference dataset is officially released.

### Processed Layer

**Append**
- Suitable for incremental processing.

**Overwrite**
- Suitable when rebuilding historical partitions.

### Analytics Layer

**Append**
- Suitable for maintaining historical analytical outputs.

**Overwrite**
- Suitable for dashboard refreshes and regenerated aggregates.

### Logs Layer

**Append**
- Preferred because each run creates additional audit records.

**Overwrite**
- Not recommended because audit history should be preserved.

---

## 5. Define retention considerations for raw data and for logs.

### Raw Data Retention

Considerations:

- Retain for auditability and governance.
- Retain long enough to support reprocessing.
- Retain for troubleshooting failed downstream jobs.
- Retain according to business and regulatory requirements.

Example:

```text
Retention: 1-7 years depending on organization policy.
```

### Log Retention

Considerations:

- Retain operational history.
- Support incident investigation.
- Support pipeline monitoring.
- Control storage costs through archival.

Example:

```text
Retention: 30-180 days for active logs.
Older logs archived to lower-cost storage.
```

---

## 6. Document the storage contract.

### Storage Contract

#### Landing Layer

Input:

```text
Daily telecom CSV files
```

Location:

```text
data/landing/
```

Rule:

```text
Temporary arrival zone for ingestion.
```

---

#### Raw Layer

Input:

```text
Validated source files
```

Location:

```text
data/raw/
```

Rule:

```text
Immutable storage.
Files must not be modified after ingestion.
```

---

#### Reference Layer

Input:

```text
Static reference datasets
```

Location:

```text
data/reference/
```

Rule:

```text
Managed separately from transactional data.
```

---

#### Processed Layer

Input:

```text
Cleaned and transformed telecom records.
```

Location:

```text
data/processed/
```

Output Examples:

```text
clean_activity.parquet
hourly_summary.parquet
```

Rule:

```text
Supports date-based partitioning.
```

---

#### Analytics Layer

Input:

```text
Processed datasets.
```

Location:

```text
data/analytics/
```

Output Examples:

```text
dashboard_summary.csv
warehouse-ready tables
```

Rule:

```text
Contains business-ready and reporting-ready data.
```

---

#### Logs Layer

Input:

```text
Pipeline execution metadata.
```

Location:

```text
logs/
```

Output Examples:

```text
ingestion_metadata.csv
Airflow execution logs
```

Rule:

```text
Append-only audit history.
```

---

# Expected Outputs

## Storage Design Diagram

```text
data/
├── landing/
├── raw/
├── reference/
│   └── milano-grid.geojson
├── processed/
│   └── year=YYYY/month=MM/day=DD/
├── analytics/
│   └── year=YYYY/month=MM/day=DD/
└── logs/
```

## Storage Contract

Defined in Question 6.
