#!/usr/bin/env python3
"""Run all SQL staging + marts + analytics models (delegates to src.etl.sql)."""
from __future__ import annotations

import sys

from src.common.logging import start_pipeline, end_pipeline
from src.config.settings import get_settings
from src.etl.sql import run_all


def main():
    s = get_settings()
    start_pipeline("run_sql")
    counts = run_all(s)
    end_pipeline("run_sql", summary={"row_counts": counts},
                 out_path=s.generated_dir / "sql_summary.json")
    print("SQL models executed:")
    for t, n in counts.items():
        print(f"  {t}: {n} rows")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"SQL pipeline FAILED: {e}", file=sys.stderr)
        sys.exit(1)
