from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    trim,
    lower,
    count,
    when
)

# Create Spark session
spark = (
    SparkSession.builder
    .appName("Spark Performance Dataset Preprocessing")
    .getOrCreate()
)

# File paths
ROOT = Path(__file__).resolve().parents[1]
input_path = str(ROOT / "data" / "performance" / "performance_dataset.csv")
output_path = str(ROOT / "data" / "performance" / "cleaned_data")

# Load dataset
df = (
    spark.read
    .option("header", "true")
    .option("inferSchema", "true")
    .csv(input_path)
)

original_rows = df.count()

print("\n========== ORIGINAL DATA ==========")
print(f"Original Rows : {original_rows}")

print("\n========== SCHEMA ==========")
df.printSchema()

print("\n========== SAMPLE DATA ==========")
df.show(10, truncate=False)

# Check missing values
print("\n========== NULL VALUES ==========")

df.select([
    count(when(col(c).isNull(), c)).alias(c)
    for c in df.columns
]).show()

# Remove duplicate rows
before = df.count()

df = df.dropDuplicates()

after = df.count()

duplicates_removed = before - after

print(f"\nDuplicate Rows Removed : {duplicates_removed}")

# Remove rows with null values
before = df.count()

df = df.dropna(
    subset=[
        "dataset_size_mb",
        "workload_type",
        "machine_type",
        "nodes",
        "runtime_minutes",
        "cost_usd",
        "source"
    ]
)

after = df.count()

null_rows_removed = before - after

print(f"Rows Removed Due To Null Values : {null_rows_removed}")

# Standardize text columns
text_columns = [
    "workload_type",
    "machine_type",
    "source"
]

for column in text_columns:
    df = df.withColumn(column, trim(lower(col(column))))

# Ensure correct data types
df = (
    df.withColumn("dataset_size_mb", col("dataset_size_mb").cast("double"))
      .withColumn("nodes", col("nodes").cast("int"))
      .withColumn("runtime_minutes", col("runtime_minutes").cast("double"))
      .withColumn("cost_usd", col("cost_usd").cast("double"))
)

# Remove invalid numeric values
df = df.filter(col("dataset_size_mb") > 0)
df = df.filter(col("nodes") > 0)
df = df.filter(col("runtime_minutes") > 0)
df = df.filter(col("runtime_minutes") < 1440)
df = df.filter(col("cost_usd") >= 0)

# Validate workload types
valid_workloads = [
    "cpu-heavy",
    "memory-heavy",
    "io-heavy",
    "cpu_heavy",
    "memory_heavy",
    "io_heavy"
]

df = df.filter(col("workload_type").isin(valid_workloads))

# Validate instance types
valid_instances = [
    "c5.xlarge",
    "c5a.xlarge",
    "c6i.xlarge",
    "m5a.xlarge",
    "m6i.xlarge",
    "r5.xlarge",
    "m5.xlarge"
]

df = df.filter(col("machine_type").isin(valid_instances))

# Remove empty strings
df = df.filter(col("workload_type") != "")
df = df.filter(col("machine_type") != "")
df = df.filter(col("source") != "")

# Cache cleaned dataset
df.cache()

final_rows = df.count()

# Display summary statistics
print("\n========== CLEANED DATA SUMMARY ==========")

df.describe().show()

# Display sample records
print("\n========== CLEANED DATA SAMPLE ==========")

df.show(10, truncate=False)

# Save clean dataset
(
    df.coalesce(1)
      .write
      .mode("overwrite")
      .option("header", "true")
      .csv(output_path)
)

# Cleaning report
print("\n========== CLEANING REPORT ==========")
print(f"Original Rows              : {original_rows}")
print(f"Duplicate Rows Removed     : {duplicates_removed}")
print(f"Rows Removed Due To Nulls  : {null_rows_removed}")
print(f"Final Rows                 : {final_rows}")
print(f"Output Location            : {output_path}")

spark.stop()
