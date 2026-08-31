"""Phase 2, question set 1-6: grid-hour telecom activity rollups and hotspot ranking."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ACTIVITY_COLUMNS = ["sms_in", "sms_out", "call_in", "call_out", "internet_activity"]


def read_landing_data(data_folder: Path) -> pd.DataFrame:
    """Read all landing CSV files and normalize the schema used across the project."""
    file_paths = sorted(data_folder.glob("sms-call-internet-mi-*.csv"))
    if not file_paths:
        raise FileNotFoundError(f"No landing files found in {data_folder}")

    frames = []
    for path in file_paths:
        df = pd.read_csv(path)
        frames.append(df)

    raw = pd.concat(frames, ignore_index=True)
    renamed = raw.rename(
        columns={
            "datetime": "timestamp",
            "CellID": "grid_id",
            "countrycode": "country_code",
            "smsin": "sms_in",
            "smsout": "sms_out",
            "callin": "call_in",
            "callout": "call_out",
            "internet": "internet_activity",
        }
    )

    renamed["timestamp"] = pd.to_datetime(renamed["timestamp"], errors="coerce")
    for column in ["grid_id", "country_code"]:
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce")
    for column in ACTIVITY_COLUMNS:
        renamed[column] = pd.to_numeric(renamed[column], errors="coerce").fillna(0.0)

    return renamed[["timestamp", "grid_id", "country_code", *ACTIVITY_COLUMNS]].copy()


# Question 1: Collapse the country-code-level records to one row per timestamp + grid_id by summing sms_in, sms_out, call_in, call_out and internet_activity across country-code categories.
def question_1_collapse_country_code_activity(raw: pd.DataFrame) -> pd.DataFrame:
    collapsed = raw.copy()
    collapsed["timestamp"] = collapsed["timestamp"].dt.floor("h")
    collapsed = collapsed.groupby(["timestamp", "grid_id"], as_index=False)[ACTIVITY_COLUMNS].sum()
    return collapsed

# Question 2: From the consolidated grid/hour DataFrame compute total SMS activity, total call activity, internet activity, total_activity, and daily activity per grid.
def question_2_derive_activity_metrics(hourly: pd.DataFrame) -> pd.DataFrame:
    hourly = hourly.copy()
    hourly["total_sms_activity"] = hourly["sms_in"] + hourly["sms_out"]
    hourly["total_call_activity"] = hourly["call_in"] + hourly["call_out"]
    hourly["total_activity"] = (
        hourly["total_sms_activity"] + hourly["total_call_activity"] + hourly["internet_activity"]
    )
    hourly["internet_share_of_total_activity"] = (
        hourly["internet_activity"] / hourly["total_activity"].replace(0, pd.NA)
    ).fillna(0.0)

    hourly["date"] = hourly["timestamp"].dt.strftime("%Y-%m-%d")
    hourly["hour"] = hourly["timestamp"].dt.hour
    return hourly

# Question 3: Identify the top ten high-activity grids for selected windows.
def question_3_hotspot_windows(hourly_summary: pd.DataFrame) -> pd.DataFrame:
    daily_activity = (
        hourly_summary.groupby(["date", "grid_id"], as_index=False)["total_activity"].sum().rename(columns={"total_activity": "daily_activity"})
    )
    daily_activity["rank"] = daily_activity.groupby("date")["daily_activity"].rank(method="first", ascending=False)
    hotspot = daily_activity[daily_activity["rank"] <= 10].sort_values(["date", "rank"]).reset_index(drop=True)
    return hotspot[["date", "grid_id", "daily_activity", "rank"]]

# Question 4: Compute the peak activity hour.
def question_4_peak_activity_hour(hourly_summary: pd.DataFrame):
    hourly_total = hourly_summary.groupby("timestamp", as_index=False)["total_activity"].sum()
    if hourly_total.empty:
        return None
    peak_row = hourly_total.sort_values(["total_activity", "timestamp"], ascending=[False, True]).iloc[0]
    return {"timestamp": peak_row["timestamp"], "total_activity": float(peak_row["total_activity"])}

# Question 5: Compute internet share of total activity.
def question_5_daily_traffic_summary(hourly_summary: pd.DataFrame) -> pd.DataFrame:
    daily = (
        hourly_summary.groupby(["date", "grid_id"], as_index=False)
        .agg(
            daily_sms_in=("sms_in", "sum"),
            daily_sms_out=("sms_out", "sum"),
            daily_call_in=("call_in", "sum"),
            daily_call_out=("call_out", "sum"),
            daily_internet_activity=("internet_activity", "sum"),
            daily_total_sms_activity=("total_sms_activity", "sum"),
            daily_total_call_activity=("total_call_activity", "sum"),
            daily_activity=("total_activity", "sum"),
        )
    )
    daily["daily_internet_share_of_total_activity"] = (
        daily["daily_internet_activity"] / daily["daily_activity"].replace(0, pd.NA)
    ).fillna(0.0)
    return daily.sort_values(["date", "grid_id"]).reset_index(drop=True)

# Question 6: Create hourly_grid_summary as the canonical downstream analytics DataFrame: exactly one record per grid_id + hourly timestamp.
def build_hourly_grid_summary(raw: pd.DataFrame) -> pd.DataFrame:
    collapsed = question_1_collapse_country_code_activity(raw)
    hourly_summary = question_2_derive_activity_metrics(collapsed)
    return hourly_summary[
        [
            "timestamp",
            "date",
            "hour",
            "grid_id",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "total_sms_activity",
            "total_call_activity",
            "total_activity",
            "internet_share_of_total_activity",
        ]
    ].sort_values(["timestamp", "grid_id"]).reset_index(drop=True)


def build_hourly_grid_summary(raw: pd.DataFrame) -> pd.DataFrame:
    """Canonical downstream analytics table: exactly one row per grid_id + hourly timestamp."""
    collapsed = question_1_collapse_country_code_activity(raw)
    hourly_summary = question_2_derive_activity_metrics(collapsed)
    return hourly_summary[
        [
            "timestamp",
            "date",
            "hour",
            "grid_id",
            "sms_in",
            "sms_out",
            "call_in",
            "call_out",
            "internet_activity",
            "total_sms_activity",
            "total_call_activity",
            "total_activity",
            "internet_share_of_total_activity",
        ]
    ].sort_values(["timestamp", "grid_id"]).reset_index(drop=True)


def write_outputs(hourly_summary: pd.DataFrame, daily_summary: pd.DataFrame, hotspot_ranking: pd.DataFrame, output_dir: Path) -> None:
    """Persist the expected output tables for downstream analytics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    hourly_summary.to_csv(output_dir / "hourly_grid_summary.csv", index=False)
    daily_summary.to_csv(output_dir / "daily_traffic_summary.csv", index=False)
    hotspot_ranking.to_csv(output_dir / "hotspot_ranking.csv", index=False)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    data_folder = root / "data" / "landing"
    output_dir = root / "PHASE_2" / "outputs" / "sp3_validation"

    raw = read_landing_data(data_folder)
    hourly_summary = build_hourly_grid_summary(raw)
    daily_summary = question_5_daily_traffic_summary(hourly_summary)
    hotspot_ranking = question_3_hotspot_windows(hourly_summary)
    peak_hour = question_4_peak_activity_hour(hourly_summary)

    write_outputs(hourly_summary, daily_summary, hotspot_ranking, output_dir)

    print("hourly_grid_summary rows:", len(hourly_summary))
    print("daily_traffic_summary rows:", len(daily_summary))
    print("hotspot_ranking rows:", len(hotspot_ranking))
    print("peak_activity_hour:", peak_hour)

    print(hourly_summary.head(5).to_string(index=False))
    print(daily_summary.head(5).to_string(index=False))
    print(hotspot_ranking.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
