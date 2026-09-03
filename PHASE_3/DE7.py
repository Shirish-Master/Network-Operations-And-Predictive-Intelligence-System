
from pathlib import Path
import json
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[1]

RAW_FILE = BASE_DIR / "data" / "raw"
PROCESSED_FILE = BASE_DIR / "data" / "processed" / "hourly_summary.parquet"
WAREHOUSE_DB = BASE_DIR / "data" / "analytics" / "warehouse.db"

STATUS_FILE = BASE_DIR / "logs" / "pipeline_status.json"

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

    status = {
    "pipeline": "telecom_ingestion",
    "timestamp": datetime.now().isoformat(),
    "status": "SUCCESS",
    "failure_type": None,
    "action": "CONTINUE",
    "processed_exists": PROCESSED_FILE.exists(),
    "warehouse_exists": WAREHOUSE_DB.exists()
    }

    if not PROCESSED_FILE.exists():

        status["status"] = "FAILED"
        status["failure_type"] = "MISSING_FILE"
        status["action"] = "FAIL"

    if not WAREHOUSE_DB.exists():

        status["status"] = "FAILED"
        status["failure_type"] = "WAREHOUSE_LOAD_FAILURE"
        status["action"] = "FAIL"

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