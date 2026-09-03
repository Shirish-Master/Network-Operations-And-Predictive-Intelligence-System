# Continuation of DE2
# 5. Create a simple Airflow DAG for detect → validate → route → log.
# 6. Run both the valid and rejected paths and inspect the result in the Airflow UI.

from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator


def detect():
    print("Detect files")


def validate():
    print("Validate files")


def route():
    print("Route files")


def log():
    print("Write metadata")


with DAG(
    dag_id="telecom_ingestion",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    schedule=None,
) as dag:

    detect_task = PythonOperator(
        task_id="detect",
        python_callable=detect,
    )

    validate_task = PythonOperator(
        task_id="validate",
        python_callable=validate,
    )

    route_task = PythonOperator(
        task_id="route",
        python_callable=route,
    )

    log_task = PythonOperator(
        task_id="log",
        python_callable=log,
    )

    # DE3 2. Add an Airflow task that launches the Spark job,
    # passing the reference path for milano-grid.geojson.

    spark_job = BashOperator(
        task_id="spark_job",
        bash_command="""
        python /mnt/c/Users/Admin/Desktop/Shirish_1/PHASE_2/spark/telecom_pipeline.py \
          --input-path /mnt/c/Users/Admin/Desktop/Shirish_1/data/raw \
          --output-path /mnt/c/Users/Admin/Desktop/Shirish_1/data
          --reference-path /mnt/c/Users/Admin/Desktop/Shirish_1/data/reference/milano-grid.geojson
        """,
    )

    # DE3 3. Make downstream tasks depend on Spark success.

    detect_task >> validate_task >> route_task >> log_task >> spark_job


# Output in ingestion_metadata.csv under logs
