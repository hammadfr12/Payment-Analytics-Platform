"""DuckDB connection helper."""
from __future__ import annotations

import duckdb
from src.config.settings import Settings, get_settings


def connect(settings: Settings | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open an in-process DuckDB connection to the project database."""
    s = settings or get_settings()
    s.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(s.duckdb_path), read_only=read_only)
