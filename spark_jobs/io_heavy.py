"""I/O-heavy Spark workload: repeated read, repartition, and write operations."""

from __future__ import annotations

import argparse
import time


from pyspark.sql import functions as F

# Supports Local, AWS EMR and Azure Databricks
try:
    from spark_jobs.common import build_spark, emit_metric, read_dataset, stop_spark_quietly
except ModuleNotFoundError:
    from common import build_spark, emit_metric, read_dataset, stop_spark_quietly

def run(input_path: str, output_path: str, partitions: int) -> None:
    spark = build_spark("cost-aware-io-heavy")
    start = time.time()
    df = read_dataset(spark, input_path)

    staged = (
        df.withColumn("event_date", F.to_date("timestamp"))
        .repartition(partitions, "region")
        .sortWithinPartitions("timestamp")
    )
    staged.write.mode("overwrite").partitionBy("region").parquet(output_path)

    reread = spark.read.parquet(output_path)
    result = reread.groupBy("region", "event_date").agg(
        F.count("*").alias("events"),
        F.sum("payload_size").alias("bytes_processed"),
    )
    rows = result.count()
    result.write.mode("overwrite").parquet(f"{output_path.rstrip('/')}_summary")
    emit_metric("io-heavy", input_path, output_path, start, rows)
    stop_spark_quietly(spark)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--partitions", type=int, default=64)
    args = parser.parse_args()
    run(args.input, args.output, args.partitions)


if __name__ == "__main__":
    main()
