"""Package Spark job modules for EMR --py-files."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def package_spark_jobs(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in (ROOT / "spark_jobs").rglob("*.py"):
            archive.write(path, path.relative_to(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a zip package for Spark job shared modules.")
    parser.add_argument("--output", default="dist/spark_jobs.zip")
    args = parser.parse_args()
    output = ROOT / args.output
    package_spark_jobs(output)
    print(output)


if __name__ == "__main__":
    main()
