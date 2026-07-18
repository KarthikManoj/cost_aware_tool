"""Upload generated datasets and Spark scripts to S3."""

from __future__ import annotations

import argparse
from pathlib import Path

import boto3


SKIP_PARTS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def should_upload(path: Path) -> bool:
    return not (SKIP_PARTS.intersection(path.parts) or path.suffix in SKIP_SUFFIXES)


def upload_path(local_path: Path, bucket: str, prefix: str) -> list[str]:
    s3 = boto3.client("s3")
    uploaded = []
    if local_path.is_file():
        if not should_upload(local_path):
            return uploaded
        key = f"{prefix.rstrip('/')}/{local_path.name}" if prefix else local_path.name
        s3.upload_file(str(local_path), bucket, key)
        uploaded.append(f"s3://{bucket}/{key}")
        return uploaded

    for file_path in local_path.rglob("*"):
        if file_path.is_file() and should_upload(file_path):
            relative = file_path.relative_to(local_path).as_posix()
            key = f"{prefix.rstrip('/')}/{relative}" if prefix else relative
            s3.upload_file(str(file_path), bucket, key)
            uploaded.append(f"s3://{bucket}/{key}")
    return uploaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload local files or folders to S3.")
    parser.add_argument("--local-path", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()

    for uri in upload_path(Path(args.local_path), args.bucket, args.prefix):
        print(uri)


if __name__ == "__main__":
    main()
