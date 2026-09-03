# README_DE2.md

## DE2 Execution Steps

### Activate Airflow Environment

```bash
cd ~/airflow-project
source airflow-venv/bin/activate
export AIRFLOW_HOME=~/airflow-home
```

### Place DAG File

Copy:

```text
telecom_ingestion_dag.py
```

to:

```text
$AIRFLOW_HOME/dags/
```

### Start Airflow

#### Terminal 1

```bash
airflow dag-processor
```

#### Terminal 2

```bash
airflow scheduler
```

#### Terminal 3

```bash
airflow api-server
```

### Open Airflow UI

```text
http://localhost:8080
```

### Verify DAG

```bash
airflow dags list
```

Expected:

```text
telecom_ingestion
```

### Run DAG

1. Open **telecom_ingestion** in Airflow UI.
2. Enable the DAG.
3. Click **Trigger**.
4. Verify successful execution of:
   - detect
   - validate
   - route
   - log

### Output Locations

Accepted files:

```text
data/raw/
```

Rejected files:

```text
data/rejected/
```

Metadata:

```text
logs/ingestion_metadata.csv
```
