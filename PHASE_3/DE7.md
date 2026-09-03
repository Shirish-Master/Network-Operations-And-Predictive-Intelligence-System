# DE7 – End-to-End Orchestration

## Implemented in Code

The following requirements are implemented in the Airflow DAG and supporting Python files:

### 1. Define the tasks: ingest → validate → spark_process → load_warehouse → quality_check → notify.

Implemented in:

```text
telecom_end_to_end_dag.py
```

Pipeline:

```text
ingest
   ↓
validate
   ↓
spark_process
   ↓
load_warehouse
   ↓
quality_check
   ↓
notify
```

---

### 2. Reuse the functions and jobs from previous labs rather than rewriting the logic.

Reused components:

```text
DE2
├── Ingestion workflow
├── Validation workflow
└── Metadata logging
```

```text
DE3
└── telecom_pipeline.py
```

```text
DE6
└── DE6.py
```

No processing logic was rewritten.

---

### 3. Add task dependencies and failure behaviour.

Dependency chain:

```text
ingest
   ↓
validate
   ↓
spark_process
   ↓
load_warehouse
   ↓
quality_check
   ↓
notify
```

Failure behavior:

```text
If any task fails, downstream tasks do not execute.
```

Examples:

```text
Validation Failure
→ spark_process not executed

Spark Failure
→ load_warehouse not executed

Warehouse Failure
→ quality_check not executed
```

---

### 4. Have quality_check write a machine-readable pipeline status record.

Implemented output:

```text
logs/pipeline_status.json
```

Example:

```json
{
    "pipeline": "telecom_end_to_end",
    "timestamp": "2026-09-02T22:15:00",
    "status": "SUCCESS",
    "processed_exists": true,
    "warehouse_exists": true
}
```

This file acts as the machine-readable evidence source for downstream consumers.

---

### 5. Add a lightweight success or failure notification or log entry.

Implemented through the notify task.

Success example:

```text
Pipeline completed successfully
```

Failure example:

```text
Pipeline failed
```

---

## Documentation

### 6. Trigger the DAG with the held-back file and trace the data from landing to warehouse.

Data Flow:

```text
Held-back Telecom CSV
          ↓
data/landing
          ↓
data/raw
          ↓
telecom_pipeline.py
          ↓
data/processed/hourly_summary.parquet
          ↓
DE6.py
          ↓
data/analytics/warehouse.db
          ↓
fact_network_activity
```

Execution Result:

```text
ingest          SUCCESS
validate        SUCCESS
spark_process   SUCCESS
load_warehouse  SUCCESS
quality_check   SUCCESS
notify          SUCCESS
```

---

### 7. Document where to troubleshoot each failure type.

#### Ingestion Failure

Check:

```text
logs/ingestion_metadata.csv
```

and

```text
ingest task logs in Airflow
```

---

#### Validation Failure

Check:

```text
validate task logs
```

and

```text
source file structure
```

---

#### Spark Processing Failure

Check:

```text
telecom_pipeline.py
```

and

```text
spark_process task logs
```

---

#### Warehouse Load Failure

Check:

```text
DE6.py
```

```text
data/analytics/warehouse.db
```

and

```text
load_warehouse task logs
```

---

#### Quality Check Failure

Check:

```text
logs/pipeline_status.json
```

and

```text
quality_check task logs
```

---

#### Notification Failure

Check:

```text
notify task logs
```

---

#### DAG Execution Failure

Check:

```text
Airflow UI
```

and

```text
Task Instance Logs
```

---

# Deliverables

## Airflow DAG

```text
telecom_end_to_end_dag.py
```

## Pipeline Status Record

```text
logs/pipeline_status.json
```

## Warehouse

```text
data/analytics/warehouse.db
```

## End-to-End Trace

```text
landing
↓
raw
↓
processed
↓
warehouse
```
