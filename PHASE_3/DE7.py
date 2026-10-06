
from pathlib import Path
import json
import csv
from datetime import datetime

import pyarrow.parquet as pq


BASE_DIR = Path(__file__).resolve().parents[1]

RAW_FILE = BASE_DIR / "data" / "raw"
PROCESSED_FILE = BASE_DIR / "data" / "processed" / "hourly_summary.parquet"
WAREHOUSE_DB = BASE_DIR / "data" / "analytics" / "warehouse.db"

STATUS_FILE = BASE_DIR / "logs" / "pipeline_status.json"
INGESTION_FILE = BASE_DIR / "logs" / "ingestion_metadata.csv"


def _ingestion_counts() -> tuple[int, int]:
    if not INGESTION_FILE.exists():
        return 0, 0
    rows_in = rows_rejected = 0
    with INGESTION_FILE.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            count = int(row.get("row_count") or 0)
            if str(row.get("status", "")).upper() == "REJECTED":
                rows_rejected += count
            else:
                rows_in += count
    return rows_in, rows_rejected

def write_pipeline_status(
    status,
    failure_type,
    action,
    processed_exists,
    warehouse_exists
):

    payload = {
        "pipeline": "telecom_ingestion",
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "failure_type": failure_type,
        "action": action,
        "processed_exists": processed_exists,
        "warehouse_exists": warehouse_exists,
    }

    STATUS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        STATUS_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(payload, file, indent=4)
        
# 4. Have quality_check write a machine-readable pipeline status record.

def quality_check():

    # DE8 10.Confirm each failure is reflected in the pipeline status record from DE7 — the assistant will read this later.

    run_timestamp = datetime.now().isoformat()
    rows_in, rows_rejected = _ingestion_counts()
    rows_published = pq.read_metadata(PROCESSED_FILE).num_rows if PROCESSED_FILE.exists() else 0
    status = {
    "pipeline": "telecom_ingestion",
    "run_id": f"telecom_ingestion-{run_timestamp}",
    "timestamp": run_timestamp,
    "status": "SUCCESS",
    "failure_type": None,
    "action": "CONTINUE",
    "processed_exists": PROCESSED_FILE.exists(),
    "warehouse_exists": WAREHOUSE_DB.exists(),
    "task_status": {"quality_check": "SUCCESS"},
    "rows_in": rows_in,
    "rows_rejected": rows_rejected,
    "nulls_handled": 0,
    "rows_published": rows_published,
    }

    if not PROCESSED_FILE.exists():

        status["status"] = "FAILED"
        status["failure_type"] = "MISSING_FILE"
        status["action"] = "FAIL"

    if not WAREHOUSE_DB.exists():

        status["status"] = "FAILED"
        status["failure_type"] = "WAREHOUSE_LOAD_FAILURE"
        status["action"] = "FAIL"

    status["task_status"]["quality_check"] = status["status"]

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(STATUS_FILE, "w", encoding="utf-8") as file:
        json.dump(status, file, indent=4)

    print("Quality check completed")
    print(status)

    return status


# 5. Add a lightweight success or failure notification or log entry.

def notify():

    if not STATUS_FILE.exists():
        raise FileNotFoundError("pipeline_status.json not found")

    with open(STATUS_FILE, "r", encoding="utf-8") as file:
        status = json.load(file)

    if status["status"] == "SUCCESS":
        print("Pipeline completed successfully")
    else:
        print("Pipeline failed")


if __name__ == "__main__":

    result = quality_check()

    notify()