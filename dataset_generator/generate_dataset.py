"""Generate realistic synthetic datasets for Spark workload experiments."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd


REGIONS = np.array(["us-east", "us-west", "eu-central", "ap-south", "ap-southeast"])
EVENT_TYPES = np.array(["login", "search", "purchase", "logout", "error", "view"])
DEVICE_TYPES = np.array(["web", "ios", "android", "api"])


def make_chunk(rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = np.datetime64("2026-01-01T00:00:00")
    timestamps = start + rng.integers(0, 60 * 60 * 24 * 30, size=rows).astype("timedelta64[s]")
    payload_sizes = rng.lognormal(mean=6.0, sigma=0.8, size=rows).astype(int)
    payload_sizes = np.clip(payload_sizes, 80, 5000)

    return pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "user_id": rng.integers(1000, 2_000_000, size=rows),
            "session_id": rng.integers(10_000, 99_999_999, size=rows),
            "region": rng.choice(REGIONS, size=rows),
            "event_type": rng.choice(EVENT_TYPES, size=rows),
            "device_type": rng.choice(DEVICE_TYPES, size=rows),
            "response_time_ms": np.clip(rng.normal(180, 75, size=rows), 5, 2500).round(2),
            "payload_size": payload_sizes,
            "amount_usd": np.where(rng.random(rows) < 0.15, rng.gamma(3.0, 20.0, rows), 0).round(2),
            "error_code": np.where(rng.random(rows) < 0.04, rng.integers(400, 599, rows), 0),
        }
    )


def generate_csv(output_path: Path, row_count: int | None, target_size_mb: float | None, chunk_rows: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    target_bytes = None if target_size_mb is None else int(target_size_mb * 1024 * 1024)
    written_rows = 0
    chunk_index = 0

    while True:
        if row_count is not None:
            remaining = row_count - written_rows
            if remaining <= 0:
                break
            rows = min(chunk_rows, remaining)
        else:
            rows = chunk_rows

        frame = make_chunk(rows, seed=42 + chunk_index)
        frame.to_csv(output_path, mode="a", header=not output_path.exists(), index=False)
        written_rows += rows
        chunk_index += 1

        if target_bytes is not None and output_path.stat().st_size >= target_bytes:
            break


def generate_parquet(output_path: Path, row_count: int, chunk_rows: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    written_rows = 0
    chunk_index = 0
    while written_rows < row_count:
        rows = min(chunk_rows, row_count - written_rows)
        frames.append(make_chunk(rows, seed=42 + chunk_index))
        written_rows += rows
        chunk_index += 1
    pd.concat(frames, ignore_index=True).to_parquet(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic workload data.")
    parser.add_argument("--output", required=True, help="Output CSV or Parquet path.")
    parser.add_argument("--rows", type=int, default=None, help="Exact number of rows to generate.")
    parser.add_argument("--target-size-mb", type=float, default=None, help="Approximate CSV file size.")
    parser.add_argument("--format", choices=["csv", "parquet"], default="csv")
    parser.add_argument("--chunk-rows", type=int, default=100_000)
    args = parser.parse_args()

    output_path = Path(args.output)
    if args.format == "parquet":
        if args.rows is None:
            raise ValueError("Parquet generation requires --rows because append-by-size is not supported.")
        generate_parquet(output_path, args.rows, args.chunk_rows)
    else:
        if args.rows is None and args.target_size_mb is None:
            raise ValueError("Provide either --rows or --target-size-mb.")
        generate_csv(output_path, args.rows, args.target_size_mb, args.chunk_rows)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Generated {output_path} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()

