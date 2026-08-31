from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
	col,
	date_trunc,
	input_file_name,
)
from pyspark.sql.types import (
	DoubleType,
	IntegerType,
	StructField,
	StructType,
	TimestampType,
)


# 1. Create a SparkSession.

spark = (
	SparkSession.builder
	.appName("MilanTelecomSP1")
	.master("local[*]")
	.getOrCreate()
)


# 2. Read the daily files from a folder using the pattern sms-call-internet-mi-*.csv. Use the -mi- in the glob — see the trap below.

data_folder = Path(__file__).resolve().parent.parent / "data" / "landing"
file_pattern = "sms-call-internet-mi-*.csv"
file_paths = [
	str(path)
	for path in sorted(data_folder.glob(file_pattern))
]
if not file_paths:
	raise FileNotFoundError(
		f"No files matched {file_pattern!r} in {data_folder}"
	)


# 3. Compare inferSchema against a trainer-provided manual StructType, and explain the cost of each.

manual_schema = StructType(
	[
		StructField("datetime", TimestampType(), nullable=True),
		StructField("CellID", IntegerType(), nullable=True),
		StructField("countrycode", IntegerType(), nullable=True),
		StructField("smsin", DoubleType(), nullable=True),
		StructField("smsout", DoubleType(), nullable=True),
		StructField("callin", DoubleType(), nullable=True),
		StructField("callout", DoubleType(), nullable=True),
		StructField("internet", DoubleType(), nullable=True),
	]
)

# inferSchema scans input data to infer types, which adds an extra pass and
# can produce inconsistent types when files contain unusual values. A manual
# StructType avoids that inference cost, documents the data contract, and is
# more predictable, but incorrect types can turn valid-looking values into nulls.

inferred_df = (
	spark.read
	.option("header", True)
	.option("inferSchema", True)
	.csv(file_paths)
)

manual_df = (
	spark.read
	.option("header", True)
	.schema(manual_schema)
	.csv(file_paths)
)

print("Inferred schema:")
inferred_df.printSchema()

print("Manual schema:")
manual_df.printSchema()

print("Schemas match:", inferred_df.schema == manual_df.schema)


# Use the manual-schema DataFrame for the remaining analysis so the pipeline
# follows the explicit project data contract.
df = manual_df


# 4. Count rows, source files, unique grids, country-code categories and distinct hourly intervals.

row_count = df.count()
source_file_count = df.select(input_file_name().alias("source_file")).distinct().count()
unique_grid_count = df.select("CellID").distinct().count()
country_code_count = df.select("countrycode").distinct().count()
hourly_interval_count = (
	df.select(date_trunc("hour", col("datetime")).alias("hour"))
	.distinct()
	.count()
)

print("Row count:", row_count)
print("Source file count:", source_file_count)
print("Unique grid count:", unique_grid_count)
print("Country-code category count:", country_code_count)
print("Distinct hourly interval count:", hourly_interval_count)


# 5. Add an input_file_name column for traceability.

df = df.withColumn("source_file", input_file_name())
df.select("source_file").show(5, truncate=False)


# 6. Inspect the partition count and explain why file layout affects Spark execution.

partition_count = df.rdd.getNumPartitions()
print("Partition count:", partition_count)
print(
	"File layout affects Spark execution because input files are split into "
	"partitions. More appropriately sized files can increase parallelism, "
	"while many tiny files add scheduling and metadata overhead. Very large "
	"unsplittable files or too few files can limit parallelism."
)


spark.stop()
