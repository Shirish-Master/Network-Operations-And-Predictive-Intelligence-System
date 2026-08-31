# It is fully to inspect and understand the raw data and specifically for one run.


# 1. Load one sms-call-internet-mi-YYYY-MM-DD.csv file with pandas and inspect shape, raw columns and dtypes.

import pandas as pd

df = pd.read_csv("../data/landing/sms-call-internet-mi-2013-11-01.csv")

print("Shape:")
print(df.shape)

print("\nRaw Columns:")
print(df.columns.tolist())

print("\nData Types:")
print(df.dtypes)


# 2. Document the raw-to-canonical mapping and standardize datetime, CellID, countrycode, smsin, smsout, callin, callout and internet into the canonical project schema.

column_mapping = {
    "datetime": "timestamp",
    "CellID": "grid_id",
    "countrycode": "country_code",
    "smsin": "sms_in",
    "smsout": "sms_out",
    "callin": "call_in",
    "callout": "call_out",
    "internet": "internet_activity"
}

print("\nRaw-to-Canonical Mapping:")

for raw_col, canonical_col in column_mapping.items():
    print(f"{raw_col} -> {canonical_col}")

df.rename(columns=column_mapping, inplace=True)

# Standardize data types
df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    errors="coerce"
)

df["grid_id"] = pd.to_numeric(
    df["grid_id"],
    errors="coerce"
)

df["country_code"] = pd.to_numeric(
    df["country_code"],
    errors="coerce"
)

activity_cols = [
    "sms_in",
    "sms_out",
    "call_in",
    "call_out",
    "internet_activity"
]

for col in activity_cols:
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )

print("\nStandardized Columns:")
print(df.columns.tolist())

print("\nStandardized Data Types:")
print(df.dtypes)


# 3. Parse the timestamp field and verify the hourly cadence in the supplied file — confirm there are exactly 24 distinct timestamps and that consecutive intervals are one hour apart. Then derive date, hour and day_of_week.

distinct_timestamps = sorted(
    df["timestamp"].dropna().unique()
)

time_diffs = (
    pd.Series(distinct_timestamps)
    .diff()
    .dropna()
)

print("\nDistinct Timestamps:")
print(len(distinct_timestamps))

print("\nConsecutive Time Differences:")
print(time_diffs.value_counts())

timestamp_count_ok = (
    len(distinct_timestamps) == 24
)

hourly_cadence_ok = (
    time_diffs.eq(
        pd.Timedelta(hours=1)
    ).all()
)

print("\nExactly 24 Distinct Timestamps:")
print(timestamp_count_ok)

print("\nAll Consecutive Intervals Are One Hour:")
print(hourly_cadence_ok)

print("\nHourly Cadence Verified:")
print(
    timestamp_count_ok
    and hourly_cadence_ok
)

df["date"] = df["timestamp"].dt.date

df["hour"] = df["timestamp"].dt.hour

df["day_of_week"] = df["timestamp"].dt.day_name()

print("\nDerived Time Columns:")
print(
    df[
        [
            "timestamp",
            "date",
            "hour",
            "day_of_week"
        ]
    ].head()
)


# 4. Check for missing grid_id, missing timestamp, blank activity measures, exact duplicates and negative activity values. Keep the raw file unchanged and document the curated-layer null policy separately.

print("\nMissing grid_id:")
print(
    df["grid_id"].isnull().sum()
)

print("\nMissing timestamp:")
print(
    df["timestamp"].isnull().sum()
)

print("\nBlank Activity Measures:")
print(
    df[activity_cols].isnull().sum()
)

print("\nExact Duplicates:")
print(
    df.duplicated().sum()
)

print("\nNegative Activity Values:")

for col in activity_cols:
    print(
        f"{col}: {(df[col] < 0).sum()}"
    )

# Grid ID range validation
invalid_grid_id = (
    df["grid_id"].notna()
    & ~df["grid_id"].between(1, 10000)
)

print("\nGrid IDs Outside the Range 1-10000:")
print(
    invalid_grid_id.sum()
)

print("\nAll Non-Null Grid IDs Within 1-10000:")
print(
    df["grid_id"]
    .dropna()
    .between(1, 10000)
    .all()
)

print("\nCurated-Layer Null Policy:")

print("""
- Preserve the raw file unchanged.
- Missing grid_id and timestamp values are treated as data-quality
  issues and excluded from the curated analytical layer as required.
- Missing activity measures are converted to zero in the curated
  layer using the documented null-to-zero rule.
- Negative activity values are treated as data-quality issues and
  investigated before downstream processing.
- Exact duplicates are checked against the expected raw grain before
  removal.
- All curated-layer exclusions and transformations are documented
  for traceability.
""")


# 5. Inspect how many country-code rows exist for the same grid and hour. Confirm the raw grain is timestamp + grid_id + country_code.

country_code_per_grid_hour = (
    df.groupby(
        ["timestamp", "grid_id"]
    )["country_code"]
    .nunique()
    .reset_index(
        name="country_code_count"
    )
)

multiple_country_codes = (
    country_code_per_grid_hour[
        country_code_per_grid_hour["country_code_count"] > 1
    ]
)

print("\nGrid-Hour Combinations with Multiple Country Codes:")
print(
    len(multiple_country_codes)
)

print("\nSample:")
print(
    multiple_country_codes.head()
)


# Check whether timestamp + grid_id + country_code uniquely identifies each row.

grain_columns = [
    "timestamp",
    "grid_id",
    "country_code"
]

grain_counts = (
    df.groupby(grain_columns)
      .size()
      .reset_index(
          name="row_count"
      )
)

grain_violations = (
    grain_counts[
        grain_counts["row_count"] > 1
    ]
)

print("\nGrain Violations:")
print(
    len(grain_violations)
)

print("\nRaw Grain:")
print(
    "timestamp + grid_id + country_code"
)

print("\nRaw Grain Is Unique:")
print(
    grain_violations.empty
)


# 6. Create total_sms, total_calls and total_activity as clearly labelled derived activity measures.

# Apply the documented curated-layer null-to-zero rule.
df[activity_cols] = df[activity_cols].fillna(0)

df["total_sms"] = (
    df["sms_in"] +
    df["sms_out"]
)

df["total_calls"] = (
    df["call_in"] +
    df["call_out"]
)

df["total_activity"] = (
    df["total_sms"] +
    df["total_calls"] +
    df["internet_activity"]
)

print("\nDerived Activity Measures:")

print(
    df[
        [
            "total_sms",
            "total_calls",
            "total_activity"
        ]
    ].head()
)


# 7. Compute the profiling facts: number of unique grids, time range, cadence, country-code categories, busiest hourly window, busiest grid, and null counts per column.

print("\nNumber of Unique Grids:")
print(
    df["grid_id"].nunique()
)

print("\nTime Range:")
print(
    df["timestamp"].min(),
    "to",
    df["timestamp"].max()
)

print("\nCadence:")
print(
    time_diffs.value_counts()
)

print("\nExactly 24 Distinct Timestamps:")
print(
    timestamp_count_ok
)

print("\nHourly Cadence Verified:")
print(
    timestamp_count_ok
    and hourly_cadence_ok
)

print("\nCountry-Code Categories:")

country_code_categories = sorted(
    df["country_code"]
    .dropna()
    .unique()
)

print(
    country_code_categories
)

print("\nNumber of Country-Code Categories:")
print(
    len(country_code_categories)
)

print("\nNull Counts Per Column:")
print(
    df.isnull().sum()
)


busiest_hour = (
    df.groupby("timestamp")["total_activity"]
      .sum()
      .sort_values(
          ascending=False
      )
)

print("\nBusiest Hourly Window:")
print(
    busiest_hour.head(1)
)


busiest_grid = (
    df.groupby("grid_id")["total_activity"]
      .sum()
      .sort_values(
          ascending=False
      )
)

print("\nBusiest Grid:")
print(
    busiest_grid.head(1)
)


# 8. Write a five-bullet data profiling summary addressed to the Network Analytics Team.

print("""
Network Analytics Team — Data Profiling Summary

* Dataset and coverage: The supplied Milan telecom activity file contains 1,891,928 rows and 8 raw columns, covering 10,000 unique grid cells across 24 hourly timestamps from 2013-11-01 00:00:00 to 2013-11-01 23:00:00.

* Time and grain validation: The file contains exactly 24 distinct timestamps, with all 23 consecutive intervals equal to one hour, confirming the expected hourly cadence. The raw grain was validated as timestamp + grid_id + country_code, with 0 grain violations. Multiple country codes occur for the same grid and hour, with 236,949 grid-hour combinations containing more than one country code, confirming that country code is part of the raw grain.

* Data-quality findings: No missing grid_id values, missing timestamps, exact duplicate rows, negative activity values, or grid IDs outside the valid 1–10,000 range were found. However, the raw activity measures contain substantial missing values: sms_in 1,086,153, sms_out 1,422,446, call_in 1,407,781, call_out 1,037,413, and internet_activity 1,087,074. These activity nulls are converted to zero in the curated layer according to the documented null-to-zero rule, while the raw file remains unchanged.

* Activity profiling: Derived measures total_sms, total_calls, and total_activity were created after applying the curated null-to-zero rule. The busiest hourly window is 2013-11-01 11:00:00, with total activity of 5,185,703.659. The busiest grid is grid_id 5161, with total activity of 274,800.2956 across the supplied hourly period.

* Country-code and downstream readiness: The dataset contains 246 distinct country-code categories. All curated exclusions and transformations should remain traceable to the raw source, with the validated grain, hourly cadence, null-handling rule, and data-quality findings carried forward as part of the curated-layer documentation.

""")