"""Spark data-quality and curated-layer pipeline for Milan telecom data."""

from __future__ import annotations

import os
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
	col,
	count,
	countDistinct,
	date_format,
	hour,
	input_file_name,
	lag,
	lit,
	min as spark_min,
	max as spark_max,
	sum as spark_sum,
	to_timestamp,
	trim,
	when,
)
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType
from pyspark.sql.window import Window


RAW_TO_CANONICAL = {
	"datetime": "timestamp",
	"CellID": "grid_id",
	"countrycode": "country_code",
	"smsin": "sms_in",
	"smsout": "sms_out",
	"callin": "call_in",
	"callout": "call_out",
	"internet": "internet_activity",
}
ACTIVITY_COLUMNS = ["sms_in", "sms_out", "call_in", "call_out", "internet_activity"]
RAW_SCHEMA = StructType(
	[StructField(column, StringType(), True) for column in RAW_TO_CANONICAL]
)


# Question 1: Rename the raw columns to the canonical names from the Core Dataset Contract.
# Question 2: Cast the activity measures to numeric types and timestamp to a usable datetime, then verify the expected hourly cadence still holds across all files.
def create_spark() -> SparkSession:
	"""Create Spark with the Windows Hadoop paths required by local mode."""
	# Hadoop installation path: C:\hadoop
	# winutils.exe location: C:\hadoop\bin\winutils.exe
	os.environ.setdefault("HADOOP_HOME", r"C:\hadoop")
	os.environ.setdefault("hadoop.home.dir", r"C:\hadoop")
	os.environ.setdefault("PATH", os.environ["PATH"] + os.pathsep + r"C:\hadoop\bin")
	return (
		SparkSession.builder.appName("MilanTelecomSP2").master("local[*]")
		.config("spark.hadoop.home.dir", r"C:\hadoop")
		.getOrCreate()
	)


def load_typed_raw(spark: SparkSession, data_folder: Path) -> DataFrame:
	"""Read all landing files as strings, rename to contract names, then cast."""
	file_paths = sorted(data_folder.glob("sms-call-internet-mi-*.csv"))
	if not file_paths:
		raise FileNotFoundError(f"No landing files found in {data_folder}")
	raw = (
		spark.read.option("header", True).schema(RAW_SCHEMA)
		.csv([str(path) for path in file_paths])
		.withColumn("source_file", input_file_name())
	)
	return (
		raw.withColumn("timestamp", to_timestamp(trim(col("datetime"))))
		.withColumn("grid_id", col("CellID").cast(IntegerType()))
		.withColumn("country_code", col("countrycode").cast(IntegerType()))
		.select(
			"timestamp", "grid_id", "country_code", *ACTIVITY_COLUMNS,
			"source_file",
		)
		.select(
			"timestamp", "grid_id", "country_code",
			*[col(column).cast(DoubleType()).alias(column) for column in ACTIVITY_COLUMNS],
			"source_file",
		)
	)


def verify_hourly_cadence(data: DataFrame) -> DataFrame:
	"""Return one cadence result per source file and a final all-files result."""
	distinct_hours = data.select("source_file", "timestamp").where(
		col("timestamp").isNotNull()
	).dropDuplicates()
	window = Window.partitionBy("source_file").orderBy("timestamp")
	gaps = (
		distinct_hours.withColumn("previous_timestamp", lag("timestamp").over(window))
		.withColumn(
			"invalid_interval",
			when(
				col("previous_timestamp").isNotNull()
				& ((col("timestamp").cast("long") - col("previous_timestamp").cast("long")) != 3600),
				1,
			).otherwise(0),
		)
	)
	return (
		gaps.groupBy("source_file")
		.agg(
			count("timestamp").alias("distinct_timestamps"),
			spark_min("timestamp").alias("time_start"),
			spark_max("timestamp").alias("time_end"),
			spark_sum("invalid_interval").alias("invalid_intervals"),
		)
		.withColumn(
			"hourly_cadence_ok",
			(col("distinct_timestamps") == 24) & (col("invalid_intervals") == 0),
		)
		.orderBy("source_file")
	)


def curate(data: DataFrame) -> tuple[DataFrame, DataFrame, DataFrame]:
	"""Preserve typed raw rows, quarantine invalid keys/negative activity, and curate."""
	# Question 3: Quarantine rows with missing grid_id or timestamp, or with negative activity values. Profile blank activity measures and apply the documented curated-layer null-to-zero rule only after raw preservation.
	flagged = data.withColumn(
		"rejection_reason",
		when(col("timestamp").isNull(), lit("missing_timestamp"))
		.when(col("grid_id").isNull(), lit("missing_grid_id"))
		.when(
			sum(when(col(column) < 0, 1).otherwise(0) for column in ACTIVITY_COLUMNS) > 0,
			lit("negative_activity"),
		),
	)
	rejected = flagged.where(col("rejection_reason").isNotNull())
	blank_profile = flagged.where(col("rejection_reason").isNull()).select(
		*[spark_sum(when(col(column).isNull(), 1).otherwise(0)).alias(column) for column in ACTIVITY_COLUMNS]
	).withColumn(
		"activity_nulls_handled",
		sum(col(column) for column in ACTIVITY_COLUMNS),
	)
	curated = (
		flagged.where(col("rejection_reason").isNull())
		.drop("rejection_reason")
		.fillna(0, subset=ACTIVITY_COLUMNS)
		.withColumn("date", date_format("timestamp", "yyyy-MM-dd"))
		.withColumn("hour", col("timestamp").cast("timestamp").substr(12, 2).cast(IntegerType()))
		.withColumn("hour", hour("timestamp"))
		.withColumn("day_of_week", date_format("timestamp", "EEEE"))
		.withColumn("total_sms", col("sms_in") + col("sms_out"))
		.withColumn("total_calls", col("call_in") + col("call_out"))
		.withColumn("total_activity", col("sms_in") + col("sms_out") + col("call_in") + col("call_out") + col("internet_activity"))
	)
	# Question 4: Create total_sms, total_calls and the project-defined total_activity indicator, while retaining the original SMS, call and internet measures.
	# Question 5: Derive date, hour and day_of_week.
	return curated, rejected, blank_profile


def run_pipeline(data_folder: Path, output_dir: Path) -> None:
	# Question 6: Compare record counts before and after cleaning, capture rejected-row counts, and report how many activity nulls the curated-layer rule handled.
	spark = create_spark()
	try:
		typed_raw = load_typed_raw(spark, data_folder).cache()
		raw_count = typed_raw.count()
		typed_raw.write.mode("overwrite").parquet(str(output_dir / "raw_preserved"))

		cadence = verify_hourly_cadence(typed_raw).cache()
		curated, rejected, blank_profile = curate(typed_raw)
		rejected_count = rejected.count()
		curated_count = curated.count()
		nulls_handled = blank_profile.first().asDict()

		output_dir.mkdir(parents=True, exist_ok=True)
		curated.write.mode("overwrite").option("header", True).csv(str(output_dir / "curated"))
		rejected.write.mode("overwrite").option("header", True).csv(str(output_dir / "quarantine"))
		cadence.write.mode("overwrite").option("header", True).csv(str(output_dir / "cadence"))
		spark.createDataFrame(
			[(raw_count, curated_count, rejected_count, nulls_handled["activity_nulls_handled"])],
			["raw_row_count", "curated_row_count", "rejected_row_count", "activity_nulls_handled"],
		).write.mode("overwrite").option("header", True).csv(str(output_dir / "metrics"))
		blank_profile.write.mode("overwrite").option("header", True).csv(str(output_dir / "blank_activity_profile"))
		print(f"Rows: raw={raw_count}, curated={curated_count}, rejected={rejected_count}")
		print(f"Activity nulls handled by curated null-to-zero rule: {nulls_handled['activity_nulls_handled']}")
		print(f"All files hourly cadence verified: {cadence.where(~col('hourly_cadence_ok')).count() == 0}")
	finally:
		spark.stop()


if __name__ == "__main__":
	root = Path(__file__).resolve().parent.parent
	run_pipeline(root / "data" / "landing", root / "PHASE_2" / "outputs" / "sp2_validation")
