"""Centralized, pure metric definitions.

Every function here is pure (no I/O, no globals) so it can be unit-tested
directly. Denominators are always protected (NULL/None on divide-by-zero).
These are the single source of truth for KPI math; SQL mirrors the same logic.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def success_rate(authorized: float, eligible: float) -> Optional[float]:
    """SR% = authorized / eligible * 100. None if eligible <= 0."""
    if eligible is None or eligible <= 0:
        return None
    return 100.0 * authorized / eligible


def failure_rate(failed: float, eligible: float) -> Optional[float]:
    """Failure rate% = failed / eligible * 100. None if eligible <= 0."""
    if eligible is None or eligible <= 0:
        return None
    return 100.0 * failed / eligible


def tpv(amounts: pd.Series) -> float:
    """TPV = SUM(amount) over eligible transactions."""
    return float(amounts.sum())


def transaction_count(ids: pd.Series) -> int:
    """Distinct transaction count."""
    return int(ids.nunique())


def aov(successful_tpv: float, successful_count: float) -> Optional[float]:
    """AOV = successful TPV / successful txn count. None on divide-by-zero."""
    if successful_count is None or successful_count <= 0:
        return None
    return successful_tpv / successful_count


def payment_method_share(method_tpv: float, total_tpv: float) -> Optional[float]:
    """Method share% = method TPV / total TPV * 100. None if total <= 0."""
    if total_tpv is None or total_tpv <= 0:
        return None
    return 100.0 * method_tpv / total_tpv


def pp_delta(current_rate: Optional[float], previous_rate: Optional[float]) -> Optional[float]:
    """Percentage-point delta = current - previous (for rates)."""
    if current_rate is None or previous_rate is None:
        return None
    return current_rate - previous_rate


def pct_delta(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Percentage delta = (current - previous) / previous * 100 (for absolute metrics).
    None where previous is zero or None."""
    if current is None or previous is None or previous == 0:
        return None
    return 100.0 * (current - previous) / previous


def checkout_conversion(successful_sessions: float, started_sessions: float) -> Optional[float]:
    """Checkout conversion% = successful sessions / started sessions * 100.
    None if started_sessions <= 0."""
    if started_sessions is None or started_sessions <= 0:
        return None
    return 100.0 * successful_sessions / started_sessions


def safe_div(num: float, den: float) -> Optional[float]:
    """Generic protected division -> None on zero/None denominator."""
    if den is None or den == 0 or num is None:
        return None
    return num / den
