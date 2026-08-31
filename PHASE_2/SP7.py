# This code has created the files saved at: C:\Users\shirish.shyam\Desktop\Shirish_1\data\processed\training_run
# Created files: clean_activity.parquet, hourly_summary.parquet, dashboard_summary.csv

"""SP7: Execute the reusable telecom pipeline against the project training folder.

Questions 1-6:
1. Create spark/telecom_pipeline.py with read_raw(), clean(), aggregate(), enrich(), write_outputs() and main().
2. Accept input, output and reference paths as arguments or configuration — nothing hardcoded.
3. Add logging for input rows, rejected rows, nulls handled, output rows, start and end time, and final status.
4. Fail cleanly and loudly when no input files are present.
5. Run the full job against the training folder.
6. Document the job contract: expected inputs, outputs and failure conditions.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PHASE_2_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_2_DIR.parent
INPUT_PATH = PROJECT_ROOT / "data" / "landing"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "training_run"
REFERENCE_PATH = PROJECT_ROOT / "data" / "reference" / "milano-grid.geojson"


def run_pipeline() -> None:
    pipeline_script = PHASE_2_DIR / "spark" / "telecom_pipeline.py"
    command = [
        sys.executable,
        str(pipeline_script),
        "--input-path",
        str(INPUT_PATH),
        "--output-path",
        str(OUTPUT_PATH),
        "--reference-path",
        str(REFERENCE_PATH),
    ]
    print("Running telecom pipeline:")
    print(" ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    run_pipeline()


if __name__ == "__main__":
    main()
