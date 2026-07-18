"""Shared Spark helpers for workload scripts."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from pyspark.sql import SparkSession


def build_spark(app_name: str) -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.shuffle.partitions", "64")
        .getOrCreate()
    )


def read_dataset(spark: SparkSession, input_path: str):
    suffix = Path(input_path).suffix.lower()
    if suffix == ".parquet" or input_path.rstrip("/").endswith("parquet"):
        return spark.read.parquet(input_path)
    return spark.read.option("header", "true").option("inferSchema", "true").csv(input_path)


def emit_metric(workload: str, input_path: str, output_path: str | None, start_time: float, rows: int) -> None:
    runtime_sec = time.time() - start_time
    print(
        json.dumps(
            {
                "workload": workload,
                "input_path": input_path,
                "output_path": output_path,
                "rows": rows,
                "runtime_seconds": round(runtime_sec, 3),
            }
        )
    )


def is_databricks_runtime(spark: SparkSession) -> bool:
    if os.environ.get("DATABRICKS_RUNTIME_VERSION") or os.environ.get("DATABRICKS_CLUSTER_ID"):
        return True
    try:
        return bool(spark.conf.get("spark.databricks.clusterUsageTags.clusterId", ""))
    except Exception:
        return False


def stop_spark_quietly(spark: SparkSession) -> None:
    if is_databricks_runtime(spark):
        print(json.dumps({"info": "spark_stop_skipped", "reason": "databricks_managed_session"}))
        return
    try:
        spark.stop()
    except Exception as exc:
        print(json.dumps({"warning": "spark_stop_failed", "message": str(exc)}))
