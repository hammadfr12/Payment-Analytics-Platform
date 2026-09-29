"""ETL: run all SQL staging + marts + analytics models in dependency order."""
from __future__ import annotations

import sys
from pathlib import Path

from src.common.db import connect
from src.common.logging import log
from src.config.settings import Settings, get_settings

SQL_ORDER = [
    "sql/staging/stg_transactions.sql",
    "sql/staging/stg_merchants.sql",
    "sql/staging/stg_checkout_events.sql",
    "sql/marts/fct_payment_performance.sql",
    "sql/marts/fct_checkout_conversion.sql",
    "sql/analytics/merchant_daily_metrics.sql",
    "sql/analytics/merchant_weekly_metrics.sql",
    "sql/analytics/industry_benchmarks.sql",
    "sql/analytics/payment_method_metrics.sql",
    "sql/analytics/rca_metrics.sql",
    "sql/analytics/opportunity_candidates.sql",
]


def _split_sql(sql: str) -> list:
    """Split SQL on ';', ignoring ';' inside line comments and string literals."""
    stmts = []
    buf = []
    in_str = False
    for line in sql.splitlines():
        if not in_str:
            in_s = False
            cut = len(line)
            for i, ch in enumerate(line):
                if ch == "'":
                    in_s = not in_s
                elif ch == "-" and i + 1 < len(line) and line[i + 1] == "-" and not in_s:
                    cut = i
                    break
            code = line[:cut]
        else:
            code = line
        buf.append(code)
        for ch in code:
            if ch == "'":
                in_str = not in_str
        if ";" in code and not in_str:
            parts = code.split(";")
            buf[-1] = parts[0]
            stmt = "\n".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def run_all(settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    con = connect(s)
    counts = {}
    try:
        for rel in SQL_ORDER:
            path = s.project_root / rel
            if not path.exists():
                raise FileNotFoundError(f"SQL file missing: {path}")
            sql = path.read_text()
            for stmt in _split_sql(sql):
                try:
                    con.execute(stmt)
                except Exception as e:
                    log("sql_error", file=rel, error=str(e))
                    raise
            log("sql_executed", file=rel)
        for t in ["stg_transactions", "stg_merchants", "stg_checkout_events",
                  "fct_payment_performance", "fct_checkout_conversion",
                  "merchant_daily_metrics", "merchant_weekly_metrics",
                  "industry_benchmarks", "payment_method_metrics",
                  "rca_metrics", "opportunity_candidates"]:
            try:
                counts[t] = int(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
            except Exception as e:
                counts[t] = f"ERROR: {e}"
    finally:
        con.close()
    return counts
