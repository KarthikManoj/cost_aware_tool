"""CPU-heavy Spark workload: repeated transformations and aggregations."""

from __future__ import annotations

import argparse

import time


from pyspark.sql import functions as F

# Supports Local, AWS EMR and Azure Databricks
try:
    from spark_jobs.common import build_spark, emit_metric, read_dataset, stop_spark_quietly
except ModuleNotFoundError:
    from common import build_spark, emit_metric, read_dataset, stop_spark_quietly

def run(input_path: str, output_path: str | None, iterations: int) -> None:
    spark = build_spark("cost-aware-cpu-heavy")
    start = time.time()
    df = read_dataset(spark, input_path)

    work = df
    for i in range(iterations):
        work = work.withColumn(
            f"score_{i}",
            (
                F.sqrt(F.col("response_time_ms") * F.col("payload_size") + F.lit(i + 1))
                + F.log1p(F.col("user_id") % F.lit(1000))
            ),
        )

    result = (
        work.groupBy("region", "event_type")
        .agg(
            F.count("*").alias("events"),
            F.avg("response_time_ms").alias("avg_response_ms"),
            F.sum("payload_size").alias("total_payload"),
            F.avg(f"score_{iterations - 1}").alias("avg_score"),
        )
        .orderBy("region", "event_type")
    )

    rows = result.count()
    if output_path:
        result.write.mode("overwrite").parquet(output_path)
    emit_metric("cpu-heavy", input_path, output_path, start, rows)
    stop_spark_quietly(spark)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--iterations", type=int, default=8)
    args = parser.parse_args()
    run(args.input, args.output, args.iterations)


if __name__ == "__main__":
    main()
