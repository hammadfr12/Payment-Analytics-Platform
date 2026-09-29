#!/usr/bin/env python3
"""Generate synthetic payment data and write Parquet to data/raw."""
from __future__ import annotations

from src.data_generation.generator import main

if __name__ == "__main__":
    main()
