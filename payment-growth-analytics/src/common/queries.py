"""Reusable DuckDB query helpers for analytics engines and the API."""
from __future__ import annotations

import re
from typing import List, Optional

import pandas as pd

from src.common.db import connect
from src.config.settings import Settings, get_settings


_NAMED_PARAM = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")


def _to_positional(sql: str, params: Optional[dict]):
    """Convert :name named params to positional ? and return (sql, list)."""
    if not params:
        return sql, []
    names = _NAMED_PARAM.findall(sql)
    if not names:
        return sql, []
    # replace each :name with ? in order
    new_sql = _NAMED_PARAM.sub("?", sql)
    return new_sql, [params[n] for n in names]


def query_df(sql: str, params=None,
             settings: Optional[Settings] = None) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame.

    `params` may be:
      - None
      - a dict of :name -> value (converted to positional ?)
      - a list/tuple of positional params for SQL already using ?
    """
    s = settings or get_settings()
    con = connect(s, read_only=True)
    try:
        if params is None:
            df = con.execute(sql).df()
        elif isinstance(params, (list, tuple)):
            df = con.execute(sql, list(params)).df()
        else:
            pos_sql, pos_params = _to_positional(sql, params)
            if pos_params:
                df = con.execute(pos_sql, pos_params).df()
            else:
                df = con.execute(pos_sql).df()
        return df
    finally:
        con.close()


def list_tables(settings: Optional[Settings] = None) -> List[str]:
    s = settings or get_settings()
    con = connect(s, read_only=True)
    try:
        rows = con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main' ORDER BY table_name"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def table_row_count(table: str, settings: Optional[Settings] = None) -> int:
    s = settings or get_settings()
    con = connect(s, read_only=True)
    try:
        return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        con.close()
