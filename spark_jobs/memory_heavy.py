"""Memory-heavy Spark workload: cache and join wide intermediate data."""

from __future__ import annotations

import argparse
import time

from pyspark.sql import functions as F

# Supports Local, AWS EMR and Azure Databricks
try:
    from spark_jobs.common import build_spark, emit_metric, read_dataset, stop_spark_quietly
except ModuleNotFoundError:
    from common import build_spark, emit_metric, read_dataset, stop_spark_quietly

def run(input_path: str, output_path: str | None) -> None:
    spark = build_spark("cost-aware-memory-heavy")
    start = time.time()
    df = read_dataset(spark, input_path)

    enriched = (
        df.withColumn("join_key", F.col("user_id") % F.lit(50_000))
        .withColumn("payload_bucket", F.floor(F.col("payload_size") / F.lit(250)))
        .select("join_key", "region", "event_type", "response_time_ms", "payload_bucket", "amount_usd")
        .cache()
    )
    enriched.count()

    profile = (
        enriched.groupBy("join_key")
        .agg(
            F.count("*").alias("user_events"),
            F.avg("response_time_ms").alias("user_avg_response"),
            F.sum("amount_usd").alias("user_revenue"),
        )
        .cache()
    )
    profile.count()

    result = (
        enriched.join(profile, "join_key")
        .groupBy("region", "event_type", "payload_bucket")
        .agg(
            F.count("*").alias("events"),
            F.avg("user_avg_response").alias("avg_profile_response"),
            F.sum("user_revenue").alias("profile_revenue"),
        )
    )

    rows = result.count()
    if output_path:
        result.write.mode("overwrite").parquet(output_path)
    emit_metric("memory-heavy", input_path, output_path, start, rows)
    stop_spark_quietly(spark)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    run(args.input, args.output)


if __name__ == "__main__":
    main()
