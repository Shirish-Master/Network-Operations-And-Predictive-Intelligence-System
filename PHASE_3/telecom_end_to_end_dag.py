#This is for DE7 and give output logs/pipeline_status.json

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator


# DE7 1. Define the tasks:
# ingest → validate → spark_process → load_warehouse → quality_check → notify.


def ingest():
    print("Reuse DE2 ingestion")


def validate():
    print("Reuse DE2 validation")


def quality_check():

    import json
    from pathlib import Path
    from datetime import datetime

    base_dir = Path("/mnt/c/Users/Admin/Desktop/Shirish_1")

    status = {
        "pipeline": "telecom_end_to_end",
        "timestamp": datetime.now().isoformat(),
        "status": "SUCCESS",
        "processed_exists": (
            base_dir / "data" / "processed" / "hourly_summary.parquet"
        ).exists(),
        "warehouse_exists": (
            base_dir / "data" / "analytics" / "warehouse.db"
        ).exists()
    }

    status_file = base_dir / "logs" / "pipeline_status.json"

    status_file.parent.mkdir(parents=True, exist_ok=True)

    with open(status_file, "w", encoding="utf-8") as file:
        json.dump(status, file, indent=4)

    print("pipeline_status.json created")


def notify():
    print("Notification generated")


with DAG(
    dag_id="telecom_end_to_end",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    schedule=None,
) as dag:

    ingest_task = PythonOperator(
        task_id="ingest",
        python_callable=ingest,
    )

    validate_task = PythonOperator(
        task_id="validate",
        python_callable=validate,
    )

    # DE7 2. Reuse the functions and jobs from previous labs.

    spark_process_task = BashOperator(
        task_id="spark_process",
        bash_command="""
        python /mnt/c/Users/Admin/Desktop/Shirish_1/PHASE_2/spark/telecom_pipeline.py \
          --input-path /mnt/c/Users/Admin/Desktop/Shirish_1/data/raw \
          --output-path /mnt/c/Users/Admin/Desktop/Shirish_1/data \
          --reference-path /mnt/c/Users/Admin/Desktop/Shirish_1/data/reference/milano-grid.geojson
        """
    )

    load_warehouse_task = BashOperator(
        task_id="load_warehouse",
        bash_command="""
        python /mnt/c/Users/Admin/Desktop/Shirish_1/PHASE_3/DE6.py
        """
    )

    quality_check_task = PythonOperator(
        task_id="quality_check",
        python_callable=quality_check,
    )

    notify_task = PythonOperator(
        task_id="notify",
        python_callable=notify,
    )

    # DE7 3. Add task dependencies and failure behaviour.
    # Airflow automatically stops downstream tasks on failure.

    (
        ingest_task
        >> validate_task
        >> spark_process_task
        >> load_warehouse_task
        >> quality_check_task
        >> notify_task
    )