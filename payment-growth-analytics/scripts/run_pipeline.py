#!/usr/bin/env python3
"""Full pipeline orchestrator: generate -> load -> sql -> rca/benchmarks/opportunities -> persist.

Usage:
  python scripts/run_pipeline.py            # uses existing raw data if present
  python scripts/run_pipeline.py --regen    # force regenerate raw data
  python scripts/run_pipeline.py --demo     # run then print demo banner
"""
from __future__ import annotations

import sys

from src.common.logging import log, start_pipeline, end_pipeline
from src.config.settings import get_settings
from src.data_generation.generator import generate_all, write_parquet
from src.etl.load import load_all
from src.etl.sql import run_all as run_sql_all
from src.analytics.benchmark import benchmark_all_merchants
from src.opportunities.engine import detect_opportunities, store_opportunities, opportunities_to_df


def main(argv=None):
    argv = argv or sys.argv[1:]
    regen = "--regen" in argv
    demo = "--demo" in argv
    s = get_settings()
    start_pipeline("full_pipeline")

    # 1. generate (or reuse)
    if regen or not (s.raw_dir / "payment_transactions.parquet").exists():
        log("pipeline_step", step="generate")
        data = generate_all(s)
        write_parquet(data, s.raw_dir)
    # 2. load
    log("pipeline_step", step="load")
    load_all(s)
    # 3. sql
    log("pipeline_step", step="sql")
    run_sql_all(s)
    # 4. benchmarks + opportunities
    log("pipeline_step", step="opportunities")
    opps = detect_opportunities(settings=s)
    store_opportunities(opps, settings=s)
    log("opportunities_generated", count=len(opps),
        critical=sum(1 for o in opps if o.severity == "Critical"),
        attention=sum(1 for o in opps if o.severity == "Attention"),
        opportunity=sum(1 for o in opps if o.severity == "Opportunity"))

    summary = {"opportunities": len(opps),
               "tables": {"merchants": 150, "transactions": "see duckdb"}}
    end_pipeline("full_pipeline", summary=summary,
                 out_path=s.generated_dir / "pipeline_summary.json")
    print(f"Pipeline complete. {len(opps)} opportunities generated.")
    if demo:
        print("DATA GENERATED")
        print("PIPELINE COMPLETE")
        print("TABLES CREATED")
    return opps


if __name__ == "__main__":
    main()
