"""FastAPI service exposing reusable payment-growth metrics.

Endpoints:
  GET /health
  GET /metrics/overview
  GET /metrics/merchant/{merchant_id}
  GET /metrics/industry/{industry}
  GET /metrics/trend
  GET /metrics/payment-method
  GET /metrics/rca
  GET /benchmarks/merchant/{merchant_id}
  GET /opportunities
  GET /opportunities/{opportunity_id}

All metrics are computed live from DuckDB (no hard-coded outputs).
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from src.analytics.benchmark import benchmark_merchant
from src.api.models import (
    HealthResponse, OverviewResponse, KpiCard, MerchantMetricsResponse,
    TrendResponse, TrendPoint, PaymentMethodResponse, PaymentMethodRow,
    RcaResponse, RcaSegment, BenchmarkResponse, OpportunityResponse,
    OpportunityListResponse,
)
from src.common.queries import query_df
from src.config.settings import Settings, get_settings
from src.opportunities.engine import detect_opportunities, load_opportunities_df
from src.rca.engine import run_rca


app = FastAPI(
    title="Payment Growth Analytics API",
    description="Reusable payment-growth metrics computed from synthetic data. "
                "All numbers originate from DuckDB; no hard-coded outputs.",
    version="1.0.0",
)


def _settings() -> Settings:
    return get_settings()


def _default_dates(s: Settings):
    df = query_df("SELECT MAX(event_date) AS maxd, MIN(event_date) AS mind "
                  "FROM fct_payment_performance", settings=s)
    end = str(df.iloc[0]["maxd"])[:10]
    start = str(df.iloc[0]["mind"])[:10]
    return start, end


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    """Health check + list of available DuckDB tables."""
    s = _settings()
    from src.common.queries import list_tables
    return HealthResponse(duckdb_path=str(s.duckdb_path), tables=list_tables(s))


@app.get("/metrics/overview", response_model=OverviewResponse, tags=["metrics"])
def metrics_overview(start_date: Optional[str] = None, end_date: Optional[str] = None,
                     merchant_id: Optional[str] = None):
    """Overall KPIs for the selected population (optional merchant filter)."""
    s = _settings()
    start, end = (start_date, end_date) if start_date and end_date else _default_dates(s)
    where = ["is_eligible = TRUE", f"event_date >= '{start}'", f"event_date <= '{end}'"]
    if merchant_id:
        where.append(f"merchant_id = '{merchant_id}'")
    where_sql = " AND ".join(where)

    df = query_df(f"""
        SELECT
            SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
            SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
            SUM(CASE WHEN is_failed     THEN 1 ELSE 0 END) AS fail,
            SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END) AS tpv,
            SUM(CASE WHEN is_authorized THEN amount ELSE 0 END) AS suc_tpv,
            COUNT(DISTINCT transaction_id) AS txn_count
        FROM fct_payment_performance
        WHERE {where_sql}
    """, settings=s)
    r = df.iloc[0]
    auth = int(r["auth"]); elig = int(r["elig"]); fail = int(r["fail"])
    tpv = float(r["tpv"]); suc_tpv = float(r["suc_tpv"]); txn = int(r["txn_count"])
    sr = (100.0 * auth / elig) if elig > 0 else None
    fr = (100.0 * fail / elig) if elig > 0 else None
    aov = (suc_tpv / auth) if auth > 0 else None

    # checkout conversion over the same window
    cc_df = query_df(f"""
        SELECT
            COUNT(DISTINCT checkout_session_id) AS started,
            COUNT(DISTINCT CASE WHEN success THEN checkout_session_id END) AS succeeded
        FROM fct_checkout_conversion
        WHERE session_date >= '{start}' AND session_date <= '{end}'
          {f"AND merchant_id = '{merchant_id}'" if merchant_id else ""}
    """, settings=s)
    cr = cc_df.iloc[0]
    started = int(cr["started"]); succeeded = int(cr["succeeded"])
    conv = (100.0 * succeeded / started) if started > 0 else None

    kpis = [
        KpiCard(metric="success_rate", value=sr, unit="percent",
                definition="authorized / eligible transactions * 100"),
        KpiCard(metric="tpv", value=tpv, unit="currency",
                definition="SUM(amount) over eligible transactions"),
        KpiCard(metric="transactions", value=txn, unit="count",
                definition="distinct transaction IDs"),
        KpiCard(metric="aov", value=aov, unit="currency",
                definition="successful TPV / successful transaction count"),
        KpiCard(metric="checkout_conversion", value=conv, unit="percent",
                definition="successful checkout sessions / started sessions * 100"),
        KpiCard(metric="failure_rate", value=fr, unit="percent",
                definition="failed eligible / eligible * 100"),
    ]
    warn = None
    if elig < s.benchmark_min_txns:
        warn = f"low_sample: only {elig} eligible txns in window"
    return OverviewResponse(start_date=start, end_date=end, kpis=kpis,
                            sample_txn_count=elig, data_quality_warning=warn)


@app.get("/metrics/merchant/{merchant_id}", response_model=MerchantMetricsResponse, tags=["metrics"])
def merchant_metrics(merchant_id: str,
                     start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Per-merchant KPIs + benchmark gap for the selected window."""
    s = _settings()
    start, end = (start_date, end_date) if start_date and end_date else _default_dates(s)
    df = query_df(f"""
        SELECT ANY_VALUE(merchant_name) AS merchant_name,
               ANY_VALUE(industry)      AS industry,
               SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
               SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
               SUM(CASE WHEN is_failed     THEN 1 ELSE 0 END) AS fail,
               SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END) AS tpv,
               SUM(CASE WHEN is_authorized THEN amount ELSE 0 END) AS suc_tpv,
               COUNT(DISTINCT transaction_id) AS txn_count
        FROM fct_payment_performance
        WHERE merchant_id = '{merchant_id}' AND is_eligible = TRUE
          AND event_date >= '{start}' AND event_date <= '{end}'
    """, settings=s)
    if df.empty or pd.isna(df.iloc[0]["elig"]) or int(df.iloc[0]["elig"]) == 0:
        raise HTTPException(404, f"merchant {merchant_id} not found in window")
    r = df.iloc[0]
    auth = int(r["auth"]); elig = int(r["elig"]); fail = int(r["fail"])
    sr = (100.0 * auth / elig) if elig > 0 else None
    fr = (100.0 * fail / elig) if elig > 0 else None
    aov = (float(r["suc_tpv"]) / auth) if auth > 0 else None

    # previous period (equal length immediately before start)
    cur_len = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    prev_end = date.fromisoformat(start) - __import__("datetime").timedelta(days=1)
    prev_start = prev_end - __import__("datetime").timedelta(days=cur_len - 1)
    prev_df = query_df(f"""
        SELECT SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
               SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig
        FROM fct_payment_performance
        WHERE merchant_id = '{merchant_id}' AND is_eligible = TRUE
          AND event_date >= '{prev_start}' AND event_date <= '{prev_end}'
    """, settings=s)
    prev_sr = None
    if not prev_df.empty and pd.notna(prev_df.iloc[0]["elig"]) and int(prev_df.iloc[0]["elig"]) > 0:
        prev_sr = 100.0 * int(prev_df.iloc[0]["auth"]) / int(prev_df.iloc[0]["elig"])
    delta = (sr - prev_sr) if (sr is not None and prev_sr is not None) else None

    bench = benchmark_merchant(merchant_id, start_date=start, end_date=end,
                               payment_method="ALL", settings=s)
    return MerchantMetricsResponse(
        merchant_id=merchant_id, merchant_name=str(r["merchant_name"]),
        industry=str(r["industry"]), start_date=start, end_date=end,
        success_rate=sr, previous_success_rate=prev_sr, sr_delta_pp=delta,
        tpv=float(r["tpv"]), transaction_count=int(r["txn_count"]),
        aov=aov, failure_rate=fr,
        benchmark_sr=bench.benchmark_sr, benchmark_gap_pp=bench.gap_pp,
        benchmark_status=bench.benchmark_status, peer_count=bench.peer_count,
        sample_txn_count=bench.sample_txn_count,
    )


@app.get("/metrics/industry/{industry}", tags=["metrics"])
def industry_metrics(industry: str,
                     start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Aggregate metrics for an industry."""
    s = _settings()
    start, end = (start_date, end_date) if start_date and end_date else _default_dates(s)
    df = query_df(f"""
        SELECT
            SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
            SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
            SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END) AS tpv,
            COUNT(DISTINCT merchant_id) AS merchants
        FROM fct_payment_performance
        WHERE industry = '{industry}' AND is_eligible = TRUE
          AND event_date >= '{start}' AND event_date <= '{end}'
    """, settings=s)
    if df.empty:
        raise HTTPException(404, f"industry {industry} not found")
    r = df.iloc[0]
    elig = int(r["elig"])
    sr = (100.0 * int(r["auth"]) / elig) if elig > 0 else None
    return {
        "industry": industry, "start_date": start, "end_date": end,
        "success_rate": sr, "tpv": float(r["tpv"]),
        "transaction_count": elig, "merchant_count": int(r["merchants"]),
    }


@app.get("/metrics/trend", response_model=TrendResponse, tags=["metrics"])
def metrics_trend(grain: str = "week",
                  merchant_id: Optional[str] = None,
                  start_date: Optional[str] = None, end_date: Optional[str] = None):
    """SR / TPV / txn count trend at daily or weekly grain."""
    s = _settings()
    start, end = (start_date, end_date) if start_date and end_date else _default_dates(s)
    if grain not in ("day", "week"):
        raise HTTPException(400, "grain must be 'day' or 'week'")
    period_col = "event_date" if grain == "day" else "week_start"
    m_filter = f"AND merchant_id = '{merchant_id}'" if merchant_id else ""
    df = query_df(f"""
        SELECT {period_col} AS period,
               SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
               SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
               SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END) AS tpv,
               COUNT(DISTINCT transaction_id) AS txn_count
        FROM fct_payment_performance
        WHERE is_eligible = TRUE
          AND event_date >= '{start}' AND event_date <= '{end}'
          {m_filter}
        GROUP BY {period_col}
        ORDER BY {period_col}
    """, settings=s)
    points = []
    for _, r in df.iterrows():
        elig = int(r["elig"])
        sr = (100.0 * int(r["auth"]) / elig) if elig > 0 else None
        points.append(TrendPoint(period=str(r["period"]), success_rate=sr,
                                 tpv=float(r["tpv"]), transaction_count=int(r["txn_count"])))
    return TrendResponse(grain=grain, merchant_id=merchant_id, points=points)


@app.get("/metrics/payment-method", response_model=PaymentMethodResponse, tags=["metrics"])
def payment_method_metrics(merchant_id: Optional[str] = None,
                           start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Per-payment-method SR / TPV / share."""
    s = _settings()
    start, end = (start_date, end_date) if start_date and end_date else _default_dates(s)
    m_filter = f"AND merchant_id = '{merchant_id}'" if merchant_id else ""
    df = query_df(f"""
        SELECT payment_method,
               SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) AS auth,
               SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END) AS elig,
               SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END) AS tpv,
               COUNT(DISTINCT transaction_id) AS txn_count
        FROM fct_payment_performance
        WHERE is_eligible = TRUE
          AND event_date >= '{start}' AND event_date <= '{end}'
          {m_filter}
        GROUP BY payment_method
    """, settings=s)
    total_tpv = float(df["tpv"].sum()) if not df.empty else 0.0
    rows = []
    for _, r in df.iterrows():
        elig = int(r["elig"])
        sr = (100.0 * int(r["auth"]) / elig) if elig > 0 else None
        share = (100.0 * float(r["tpv"]) / total_tpv) if total_tpv > 0 else None
        rows.append(PaymentMethodRow(
            payment_method=str(r["payment_method"]), success_rate=sr,
            tpv=float(r["tpv"]), transaction_count=int(r["txn_count"]),
            tpv_share_pct=share,
        ))
    return PaymentMethodResponse(merchant_id=merchant_id, rows=rows)


@app.get("/metrics/rca", response_model=RcaResponse, tags=["metrics"])
def metrics_rca(merchant_id: str = Query(..., description="Target merchant ID"),
                current_start: Optional[str] = None,
                current_end: Optional[str] = None):
    """RCA contribution decomposition for a merchant (latest 2w vs prior 2w)."""
    s = _settings()
    if not (current_start and current_end):
        from src.opportunities.engine import _latest_two_weeks
        current_start, current_end, prev_start, prev_end = _latest_two_weeks(s)
    else:
        cur_len = (date.fromisoformat(current_end) - date.fromisoformat(current_start)).days + 1
        prev_end = date.fromisoformat(current_start) - __import__("datetime").timedelta(days=1)
        prev_start = prev_end - __import__("datetime").timedelta(days=cur_len - 1)
        prev_start, prev_end = str(prev_start), str(prev_end)
    try:
        rca = run_rca(merchant_id, current_start, current_end, prev_start, prev_end, settings=s)
    except Exception as e:
        raise HTTPException(500, f"RCA failed: {e}")
    top = [RcaSegment(
        dimension=c["dimension"], segment=c["segment"],
        current_sr=c["current_sr"], previous_sr=c["previous_sr"],
        delta_pp=c["delta_pp"], contribution=c["contribution"],
        share_of_decline=c["share_of_decline"],
        volume_current=c["volume_current"], volume_previous=c["volume_previous"],
    ) for c in rca.top_contributors]
    return RcaResponse(
        merchant_id=merchant_id,
        current_period=f"{current_start}..{current_end}",
        previous_period=f"{prev_start}..{prev_end}",
        overall_current_sr=rca.overall_current_sr,
        overall_previous_sr=rca.overall_previous_sr,
        overall_delta_pp=rca.overall_delta_pp,
        top_contributors=top, language_note=rca.language_note,
    )


@app.get("/benchmarks/merchant/{merchant_id}", response_model=BenchmarkResponse, tags=["benchmarks"])
def merchant_benchmark(merchant_id: str,
                       start_date: Optional[str] = None, end_date: Optional[str] = None,
                       payment_method: Optional[str] = Query("ALL")):
    """Benchmark a merchant against industry + country + payment_method peers."""
    s = _settings()
    start, end = (start_date, end_date) if start_date and end_date else _default_dates(s)
    b = benchmark_merchant(merchant_id, start_date=start, end_date=end,
                           payment_method=payment_method, settings=s)
    return BenchmarkResponse(
        merchant_id=b.merchant_id, industry=b.industry, country=b.country,
        payment_method=b.payment_method, merchant_sr=b.merchant_sr,
        benchmark_sr=b.benchmark_sr, gap_pp=b.gap_pp, peer_count=b.peer_count,
        sample_txn_count=b.sample_txn_count, benchmark_status=b.benchmark_status,
        methodology=b.methodology,
    )


def _load_opportunities_df(s: Settings):
    """Read persisted opportunities from DuckDB (delegates to engine)."""
    return load_opportunities_df(s)


@app.get("/opportunities", response_model=OpportunityListResponse, tags=["opportunities"])
def list_opportunities(severity: Optional[str] = None,
                       opportunity_type: Optional[str] = None,
                       merchant_id: Optional[str] = None):
    """List all opportunities (optionally filtered) from the persisted table."""
    s = _settings()
    df = _load_opportunities_df(s)
    if severity:
        df = df[df["severity"] == severity]
    if opportunity_type:
        df = df[df["opportunity_type"] == opportunity_type]
    if merchant_id:
        df = df[df["merchant_id"] == merchant_id]
    items = [OpportunityResponse(**row.to_dict()) for _, row in df.iterrows()]
    return OpportunityListResponse(count=len(items), opportunities=items)


@app.get("/opportunities/{opportunity_id}", response_model=OpportunityResponse, tags=["opportunities"])
def get_opportunity(opportunity_id: str):
    """Fetch a single opportunity by ID from the persisted table."""
    s = _settings()
    df = _load_opportunities_df(s)
    df = df[df["opportunity_id"] == opportunity_id]
    if df.empty:
        raise HTTPException(404, f"opportunity {opportunity_id} not found")
    return OpportunityResponse(**df.iloc[0].to_dict())


if __name__ == "__main__":
    import uvicorn
    s = _settings()
    uvicorn.run("src.api.main:app", host=s.api_host, port=s.api_port, reload=False)
