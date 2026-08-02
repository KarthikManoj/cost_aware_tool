from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    trim,
    lower,
    count,
    when
)

# ----------------------------------------------------
# Create Spark Session
# ----------------------------------------------------
spark = (
    SparkSession.builder
    .appName("Spark Performance Dataset Preprocessing")
    .getOrCreate()
)

# ----------------------------------------------------
# File Paths
# ----------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
input_path = str(ROOT / "data" / "performance" / "performance_dataset.csv")
output_path = str(ROOT / "data" / "performance" / "cleaned_data")

# ----------------------------------------------------
# Load Dataset
# ----------------------------------------------------
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

# ----------------------------------------------------
# Check Missing Values
# ----------------------------------------------------
print("\n========== NULL VALUES ==========")

df.select([
    count(when(col(c).isNull(), c)).alias(c)
    for c in df.columns
]).show()

# ----------------------------------------------------
# Remove Duplicate Rows
# ----------------------------------------------------
before = df.count()

df = df.dropDuplicates()

after = df.count()

duplicates_removed = before - after

print(f"\nDuplicate Rows Removed : {duplicates_removed}")

# ----------------------------------------------------
# Remove Rows with Null Values
# ----------------------------------------------------
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

# ----------------------------------------------------
# Standardize Text Columns
# ----------------------------------------------------
text_columns = [
    "workload_type",
    "machine_type",
    "source"
]

for column in text_columns:
    df = df.withColumn(column, trim(lower(col(column))))

# ----------------------------------------------------
# Ensure Correct Data Types
# ----------------------------------------------------
df = (
    df.withColumn("dataset_size_mb", col("dataset_size_mb").cast("double"))
      .withColumn("nodes", col("nodes").cast("int"))
      .withColumn("runtime_minutes", col("runtime_minutes").cast("double"))
      .withColumn("cost_usd", col("cost_usd").cast("double"))
)

# ----------------------------------------------------
# Remove Invalid Numeric Values
# ----------------------------------------------------
df = df.filter(col("dataset_size_mb") > 0)
df = df.filter(col("nodes") > 0)
df = df.filter(col("runtime_minutes") > 0)
df = df.filter(col("runtime_minutes") < 1440)
df = df.filter(col("cost_usd") >= 0)

# ----------------------------------------------------
# Validate Workload Types
# ----------------------------------------------------
valid_workloads = [
    "cpu-heavy",
    "memory-heavy",
    "io-heavy",
    "cpu_heavy",
    "memory_heavy",
    "io_heavy"
]

df = df.filter(col("workload_type").isin(valid_workloads))

# ----------------------------------------------------
# Validate Instance Types
# ----------------------------------------------------
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

# ----------------------------------------------------
# Remove Empty Strings
# ----------------------------------------------------
df = df.filter(col("workload_type") != "")
df = df.filter(col("machine_type") != "")
df = df.filter(col("source") != "")

# ----------------------------------------------------
# Cache Cleaned Dataset
# ----------------------------------------------------
df.cache()

final_rows = df.count()

# ----------------------------------------------------
# Display Summary Statistics
# ----------------------------------------------------
print("\n========== CLEANED DATA SUMMARY ==========")

df.describe().show()

# ----------------------------------------------------
# Display Sample Records
# ----------------------------------------------------
print("\n========== CLEANED DATA SAMPLE ==========")

df.show(10, truncate=False)

# ----------------------------------------------------
# Save Clean Dataset
# ----------------------------------------------------
(
    df.coalesce(1)
      .write
      .mode("overwrite")
      .option("header", "true")
      .csv(output_path)
)

# ----------------------------------------------------
# Cleaning Report
# ----------------------------------------------------
print("\n========== CLEANING REPORT ==========")
print(f"Original Rows              : {original_rows}")
print(f"Duplicate Rows Removed     : {duplicates_removed}")
print(f"Rows Removed Due To Nulls  : {null_rows_removed}")
print(f"Final Rows                 : {final_rows}")
print(f"Output Location            : {output_path}")

spark.stop()
