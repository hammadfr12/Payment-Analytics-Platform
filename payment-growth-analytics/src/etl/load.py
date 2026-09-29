"""ETL: load raw Parquet into DuckDB raw_* / dim_* tables."""
from __future__ import annotations

import pandas as pd

from src.common.db import connect
from src.common.logging import log
from src.config.settings import Settings, get_settings

RAW_TABLES = {
    "merchants": "raw_merchants",
    "payment_transactions": "raw_payment_transactions",
    "checkout_events": "raw_checkout_events",
    "error_codes": "dim_error_codes",
    "payment_methods": "dim_payment_methods",
    "calendar": "dim_calendar",
}


def load_all(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    con = connect(s)
    try:
        for tgt in RAW_TABLES.values():
            con.execute(f"DROP TABLE IF EXISTS {tgt}")
        counts = {}
        for name, table in RAW_TABLES.items():
            path = s.raw_dir / f"{name}.parquet"
            if not path.exists():
                raise FileNotFoundError(f"Missing raw file: {path}. Run generate-data first.")
            df = pd.read_parquet(path)
            con.register(f"df_{name}", df)
            con.execute(f"CREATE TABLE {table} AS SELECT * FROM df_{name}")
            counts[table] = len(df)
            con.unregister(f"df_{name}")
            log("load_table", table=table, rows=len(df))
    finally:
        con.close()
    return counts
