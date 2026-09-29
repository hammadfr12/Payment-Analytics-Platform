#!/usr/bin/env python3
"""Load raw Parquet files into DuckDB (delegates to src.etl.load)."""
from __future__ import annotations

from src.common.logging import start_pipeline, end_pipeline
from src.config.settings import get_settings
from src.etl.load import load_all


def main():
    s = get_settings()
    start_pipeline("load_data")
    counts = load_all(s)
    end_pipeline("load_data", summary={"tables": counts},
                 out_path=s.generated_dir / "load_summary.json")
    print("Loaded raw tables into DuckDB:")
    for t, n in counts.items():
        print(f"  {t}: {n} rows")


if __name__ == "__main__":
    main()
