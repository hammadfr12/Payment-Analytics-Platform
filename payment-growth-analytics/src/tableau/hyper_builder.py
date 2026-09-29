"""Build a Tableau Hyper extract from the analytical tables in DuckDB.

Produces a single .hyper file containing multiple tables (one per logical
dataset required by the PRD):
  - Merchant Performance   (merchant_weekly_metrics)
  - Industry Benchmark     (industry_benchmarks)
  - RCA                    (rca_metrics)
  - Opportunities          (opportunities_final)
  - Checkout Conversion    (fct_checkout_conversion aggregated)
  - Payment Method Metrics (payment_method_metrics)
  - Merchants (dim)        (stg_merchants)

Uses the tableauhyperapi to define explicit table schemas and insert rows.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from tableauhyperapi import (
    HyperProcess, Connection, CreateMode, Telemetry,
    TableName, TableDefinition, SqlType, Inserter,
    NOT_NULLABLE, NULLABLE,
)

from src.common.db import connect
from src.common.logging import log, start_pipeline, end_pipeline
from src.config.settings import Settings, get_settings


# Map pandas/Python dtypes to Hyper SqlType
def _sql_type(dtype, sample) -> SqlType:
    s = str(dtype)
    if "int" in s:
        return SqlType.big_int()
    if "float" in s:
        return SqlType.double()
    if "datetime" in s or "date" in s:
        return SqlType.timestamp()
    if "bool" in s:
        return SqlType.bool()
    # string fallback
    return SqlType.varchar(255)


def _define_table(name: str, df: pd.DataFrame) -> TableDefinition:
    table = TableDefinition(TableName(name))
    for col in df.columns:
        series = df[col]
        # Pandas 'object' may hold strings or None; treat as varchar
        if str(series.dtype) == "object":
            stype = SqlType.varchar(255)
        elif "int" in str(series.dtype):
            stype = SqlType.big_int()
        elif "float" in str(series.dtype):
            stype = SqlType.double()
        elif "datetime" in str(series.dtype) or "date" in str(series.dtype):
            stype = SqlType.timestamp()
        elif "bool" in str(series.dtype):
            stype = SqlType.bool()
        else:
            stype = SqlType.varchar(255)
        table.add_column(col.replace(" ", "_"), stype, NULLABLE)
    return table


def _insert_rows(con: Connection, table: TableDefinition, df: pd.DataFrame) -> int:
    """Insert df rows into the Hyper table with robust NA/None handling.

    Uses per-column normalization to plain python lists for speed; converts
    pandas NA/NaN/NaT to None and Timestamps to python datetimes.
    """
    cols = list(df.columns)
    n = len(df)
    norm_cols = []
    for c in cols:
        s = df[c]
        if str(s.dtype) == "object":
            norm_cols.append([None if (v is None or v is pd.NA or (isinstance(v, float) and pd.isna(v))) else
                              (v.to_pydatetime() if isinstance(v, pd.Timestamp) else
                               (str(v) if not isinstance(v, (str, int, float, bool)) else v))
                              for v in s.values])
        elif "datetime" in str(s.dtype) or "date" in str(s.dtype):
            arr = s.values
            norm_cols.append([None if pd.isna(t) else pd.Timestamp(t).to_pydatetime() for t in arr])
        elif "float" in str(s.dtype):
            arr = s.values
            norm_cols.append([None if pd.isna(x) else float(x) for x in arr])
        elif "int" in str(s.dtype):
            norm_cols.append([int(x) for x in s.values])
        elif "bool" in str(s.dtype):
            norm_cols.append([None if pd.isna(x) else bool(x) for x in s.values])
        else:
            norm_cols.append([None if pd.isna(v) else v for v in s.values])

    with Inserter(con, table) as ins:
        for i in range(n):
            ins.add_row([norm_cols[j][i] for j in range(len(cols))])
        ins.execute()
    return n


# Datasets to publish. Each is (hyper_table_name, sql_to_load_df)
DATASETS = [
    ("merchant_performance",
     "SELECT * FROM merchant_weekly_metrics"),
    ("industry_benchmark",
     "SELECT * FROM industry_benchmarks"),
    ("rca",
     "SELECT * FROM rca_metrics"),
    ("opportunities",
     "SELECT * FROM opportunities_final"),
    ("checkout_conversion",
     """
     SELECT merchant_id, week_start,
            COUNT(*) AS sessions_started,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) AS successful_sessions,
            SUM(CASE WHEN attempted THEN 1 ELSE 0 END) AS attempted_sessions
     FROM fct_checkout_conversion
     GROUP BY merchant_id, week_start
     """),
    ("payment_method_metrics",
     "SELECT * FROM payment_method_metrics"),
    ("merchants",
     "SELECT * FROM stg_merchants"),
]


def build_hyper(settings: Optional[Settings] = None) -> Path:
    s = settings or get_settings()
    start_pipeline("build_hyper")
    hyper_path = s.hyper_path
    hyper_path.parent.mkdir(parents=True, exist_ok=True)
    # remove old extract
    if hyper_path.exists():
        hyper_path.unlink()

    # load datasets from DuckDB
    con = connect(s, read_only=True)
    datasets: Dict[str, pd.DataFrame] = {}
    try:
        for name, sql in DATASETS:
            try:
                df = con.execute(sql).df()
            except Exception as e:
                log("hyper_dataset_skip", name=name, error=str(e))
                continue
            datasets[name] = df
            log("hyper_dataset_loaded", name=name, rows=len(df))
    finally:
        con.close()

    # build hyper
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with Connection(hp.endpoint, str(hyper_path), CreateMode.CREATE_AND_REPLACE) as hcon:
            counts = {}
            for name, df in datasets.items():
                if df.empty:
                    continue
                table_def = _define_table(name, df)
                hcon.catalog.create_table(table_def)
                n = _insert_rows(hcon, table_def, df)
                counts[name] = n
                log("hyper_table_written", name=name, rows=n)
            # create a small metadata table
            meta_def = TableDefinition(TableName("_extract_metadata"))
            meta_def.add_column("dataset", SqlType.varchar(100), NOT_NULLABLE)
            meta_def.add_column("row_count", SqlType.big_int(), NOT_NULLABLE)
            hcon.catalog.create_table(meta_def)
            with Inserter(hcon, meta_def) as ins:
                for k, v in counts.items():
                    ins.add_row([k, v])
                ins.execute()

    summary = {"hyper_path": str(hyper_path), "tables": counts}
    end_pipeline("build_hyper", summary=summary,
                 out_path=s.generated_dir / "hyper_summary.json")
    log("hyper_complete", path=str(hyper_path), tables=list(counts.keys()))
    return hyper_path


def main():
    path = build_hyper()
    print(f"Hyper extract created: {path}")
    print(f"  size: {path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
