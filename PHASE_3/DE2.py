# 2. Create one valid and one intentionally invalid training file. The invalid file should break something specific and named — a missing column, a malformed timestamp, or a negative activity value. 
# Here we named the sms-call-internet-mi-2013-11-01.csv as sms-call-internet-mi-valid and sms-call-internet-mi-2013-11-02.csv as sms-call-internet-mi-invalid.csv and in invalid file in the second row have entered a negative value in internet column to be invalid.
from pathlib import Path
from datetime import datetime
import shutil
import pandas as pd

# 1. Create data/landing/, data/raw/, data/rejected/, data/reference/ and logs/. Place milano-grid.geojson in data/reference/ as a static reference asset. 
ROOT = Path(__file__).resolve().parent.parent

LANDING = ROOT / "data" / "landing"
RAW = ROOT / "data" / "raw"
REJECTED = ROOT / "data" / "rejected"
LOGS = ROOT / "logs"

REQUIRED_COLUMNS = [
    "datetime",
    "CellID",
    "countrycode",
    "smsin",
    "smsout",
    "callin",
    "callout",
    "internet"
]

# 3. Implement detect_files(), validate_schema(), validate_minimum_quality() and route_file() for the daily activity CSVs. Detect using the pattern sms-call-internet-mi-*.csv. Do not treat the GeoJSON reference as a daily ingest candidate. 
def detect_files():
    """Find telecom CSV files only."""
    return sorted(
        LANDING.glob("sms-call-internet-mi-*.csv")
    )


def validate_schema(file_path):
    """Check required columns exist."""

    try:
        df = pd.read_csv(file_path, nrows=5)

        missing = [
            col
            for col in REQUIRED_COLUMNS
            if col not in df.columns
        ]

        if missing:
            return False, f"Missing columns: {missing}"

        return True, "Schema valid"

    except Exception as e:
        return False, str(e)


def validate_minimum_quality(file_path):
    """Check timestamps and negative activity."""

    try:
        df = pd.read_csv(file_path)

        timestamps = pd.to_datetime(
            df["datetime"],
            errors="coerce"
        )

        if timestamps.isna().any():
            return False, "Malformed timestamp"

        activity_columns = [
            "smsin",
            "smsout",
            "callin",
            "callout",
            "internet"
        ]

        for col in activity_columns:

            numeric_col = pd.to_numeric(
                df[col],
                errors="coerce"
            )

            if (numeric_col < 0).any():
                return False, f"Negative value found in {col}"

        return True, "Quality valid"

    except Exception as e:
        return False, str(e)


def route_file(file_path, accepted):
    """Move file to raw or rejected."""

    destination = (
        RAW / file_path.name
        if accepted
        else REJECTED / file_path.name
    )

    shutil.copy2(
        file_path,
        destination
    )

    return destination

#4. Write ingestion metadata for every file seen: filename, status, row_count, reason, processed_at. 
def write_metadata(
    filename,
    status,
    row_count,
    reason
):
    """Append ingestion metadata."""

    metadata_file = (
        LOGS / "ingestion_metadata.csv"
    )

    record = pd.DataFrame(
        [
            {
                "filename": filename,
                "status": status,
                "row_count": row_count,
                "reason": reason,
                "processed_at":
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
            }
        ]
    )

    if metadata_file.exists():
        record.to_csv(
            metadata_file,
            mode="a",
            header=False,
            index=False
        )
    else:
        record.to_csv(
            metadata_file,
            index=False
        )


def process_file(file_path):

    row_count = len(
        pd.read_csv(file_path)
    )

    schema_ok, schema_reason = (
        validate_schema(file_path)
    )

    if not schema_ok:

        route_file(
            file_path,
            accepted=False
        )

        write_metadata(
            file_path.name,
            "REJECTED",
            row_count,
            schema_reason
        )

        return

    quality_ok, quality_reason = (
        validate_minimum_quality(
            file_path
        )
    )

    if not quality_ok:

        route_file(
            file_path,
            accepted=False
        )

        write_metadata(
            file_path.name,
            "REJECTED",
            row_count,
            quality_reason
        )

        return

    route_file(
        file_path,
        accepted=True
    )

    write_metadata(
        file_path.name,
        "ACCEPTED",
        row_count,
        "Passed validation"
    )


def main():

    RAW.mkdir(
        parents=True,
        exist_ok=True
    )

    REJECTED.mkdir(
        parents=True,
        exist_ok=True
    )

    LOGS.mkdir(
        parents=True,
        exist_ok=True
    )

    files = detect_files()

    print(
        f"Files detected: {len(files)}"
    )

    for file_path in files:

        print(
            f"Processing {file_path.name}"
        )

        process_file(file_path)

    print("Ingestion complete")


if __name__ == "__main__":
    main()