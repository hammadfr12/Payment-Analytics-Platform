"""Benchmark engine.

Benchmarks a merchant against: industry + country + payment method + date range,
using a *weighted aggregate* SR (weighted by eligible transaction volume), with:
  - minimum transaction threshold
  - minimum peer (merchant) count
  - self-exclusion (the target merchant is never in its own peer group)
  - benchmark_status: VALID | INSUFFICIENT_SAMPLE | NO_PEERS
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional

import pandas as pd

from src.common.queries import query_df
from src.config.settings import Settings, get_settings


@dataclass
class BenchmarkResult:
    merchant_id: str
    industry: str
    country: str
    payment_method: Optional[str]
    merchant_sr: Optional[float]
    benchmark_sr: Optional[float]
    gap_pp: Optional[float]
    peer_count: int
    sample_txn_count: int
    merchant_txn_count: int
    benchmark_status: str
    methodology: str


METHODOLOGY = (
    "Weighted aggregate SR over the peer group = industry + country + "
    "payment_method + date range, excluding the target merchant. "
    "VALID requires peer_count >= min_peers AND sample_txn_count >= min_txns."
)


def _where_payment_method(payment_method: Optional[str]) -> str:
    if payment_method is None or payment_method == "ALL":
        return ""
    return " AND payment_method = :payment_method"


def benchmark_merchant(
    merchant_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    payment_method: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> BenchmarkResult:
    """Compute a single merchant's benchmark for the given filters."""
    s = settings or get_settings()

    pm_filter = _where_payment_method(payment_method)
    date_filter = ""
    if start_date:
        date_filter += " AND event_date >= :start_date"
    if end_date:
        date_filter += " AND event_date <= :end_date"

    # Merchant's own SR
    merchant_sql = f"""
        SELECT
            ANY_VALUE(m.industry) AS industry,
            ANY_VALUE(m.country)  AS country,
            SUM(CASE WHEN f.is_eligible   THEN 1 ELSE 0 END) AS merchant_eligible,
            SUM(CASE WHEN f.is_authorized THEN 1 ELSE 0 END) AS merchant_authorized
        FROM fct_payment_performance f
        JOIN stg_merchants m ON f.merchant_id = m.merchant_id
        WHERE f.merchant_id = :merchant_id
          AND f.is_eligible = TRUE
          {date_filter}
          {pm_filter}
    """
    params = {"merchant_id": merchant_id}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if payment_method and payment_method != "ALL":
        params["payment_method"] = payment_method

    mdf = query_df(merchant_sql, params, settings=s)
    if mdf.empty:
        return BenchmarkResult(
            merchant_id=merchant_id, industry=None, country=None,
            payment_method=payment_method, merchant_sr=None, benchmark_sr=None,
            gap_pp=None, peer_count=0, sample_txn_count=0, merchant_txn_count=0,
            benchmark_status="NO_PEERS", methodology=METHODOLOGY,
        )

    industry = mdf.iloc[0]["industry"]
    country = mdf.iloc[0]["country"]
    m_elig = int(mdf.iloc[0]["merchant_eligible"])
    m_auth = int(mdf.iloc[0]["merchant_authorized"])
    merchant_sr = (100.0 * m_auth / m_elig) if m_elig > 0 else None

    # Peer group: same industry + country, same payment_method (if specified),
    # EXCLUDING the target merchant.
    peer_sql = f"""
        SELECT
            f.merchant_id,
            SUM(CASE WHEN f.is_eligible   THEN 1 ELSE 0 END) AS elig,
            SUM(CASE WHEN f.is_authorized THEN 1 ELSE 0 END) AS auth
        FROM fct_payment_performance f
        JOIN stg_merchants m ON f.merchant_id = m.merchant_id
        WHERE m.industry = :industry
          AND m.country = :country
          AND f.merchant_id <> :merchant_id
          AND f.is_eligible = TRUE
          {date_filter}
          {pm_filter}
        GROUP BY f.merchant_id
    """
    peer_params = {"industry": industry, "country": country, "merchant_id": merchant_id}
    if start_date:
        peer_params["start_date"] = start_date
    if end_date:
        peer_params["end_date"] = end_date
    if payment_method and payment_method != "ALL":
        peer_params["payment_method"] = payment_method

    pdf = query_df(peer_sql, peer_params, settings=s)
    peer_count = int(len(pdf))
    sample_txn_count = int(pdf["elig"].sum()) if not pdf.empty else 0

    # weighted aggregate SR
    if not pdf.empty and pdf["elig"].sum() > 0:
        benchmark_sr = 100.0 * pdf["auth"].sum() / pdf["elig"].sum()
    else:
        benchmark_sr = None

    # status
    if peer_count < s.benchmark_min_peers or sample_txn_count < s.benchmark_min_txns:
        status = "INSUFFICIENT_SAMPLE" if peer_count > 0 else "NO_PEERS"
    else:
        status = "VALID"

    gap_pp = (merchant_sr - benchmark_sr) if (merchant_sr is not None and benchmark_sr is not None) else None

    return BenchmarkResult(
        merchant_id=merchant_id, industry=industry, country=country,
        payment_method=payment_method, merchant_sr=merchant_sr,
        benchmark_sr=benchmark_sr, gap_pp=gap_pp, peer_count=peer_count,
        sample_txn_count=sample_txn_count, merchant_txn_count=m_elig,
        benchmark_status=status, methodology=METHODOLOGY,
    )


def benchmark_all_merchants(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> pd.DataFrame:
    """Compute a per-merchant (all-method) benchmark for the date range.

    Useful for the Opportunity engine and the Benchmarking dashboard tab.
    """
    s = settings or get_settings()
    merchants = query_df("SELECT merchant_id FROM stg_merchants ORDER BY merchant_id", settings=s)
    rows = []
    for mid in merchants["merchant_id"].tolist():
        r = benchmark_merchant(mid, start_date=start_date, end_date=end_date,
                               payment_method="ALL", settings=s)
        rows.append(asdict(r))
    return pd.DataFrame(rows)
