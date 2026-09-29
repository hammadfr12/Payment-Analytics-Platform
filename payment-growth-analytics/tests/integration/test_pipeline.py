"""Integration test: verify the full pipeline artifacts exist and are consistent.

Assumes the pipeline has already run (data/processed/payment_growth.duckdb and
tableau/extracts/payment_growth.hyper exist). Skips gracefully if not.
"""
from __future__ import annotations

import pytest

from src.common.queries import query_df, list_tables
from src.config.settings import get_settings

s = get_settings()

pytestmark = pytest.mark.skipif(
    not s.duckdb_path.exists(),
    reason="DuckDB not built; run `make run-pipeline` first",
)


def test_duckdb_exists():
    assert s.duckdb_path.exists()


def test_all_analytical_tables_present():
    tables = set(list_tables(s))
    expected = {
        "raw_payment_transactions", "raw_merchants", "raw_checkout_events",
        "fct_payment_performance", "fct_checkout_conversion",
        "merchant_daily_metrics", "merchant_weekly_metrics",
        "industry_benchmarks", "payment_method_metrics", "rca_metrics",
        "opportunity_candidates",
    }
    assert expected.issubset(tables), f"missing: {expected - tables}"


def test_fct_payment_performance_populated():
    n = query_df("SELECT COUNT(*) AS n FROM fct_payment_performance", settings=s).iloc[0]["n"]
    assert int(n) > 100_000


def test_merchant_weekly_metrics_have_sensible_sr():
    r = query_df("""
        SELECT MIN(success_rate) AS mn, MAX(success_rate) AS mx
        FROM merchant_weekly_metrics WHERE success_rate IS NOT NULL
    """, settings=s).iloc[0]
    assert 0 <= float(r["mn"]) <= 100
    assert 0 <= float(r["mx"]) <= 100


def test_industry_benchmarks_have_peer_counts():
    r = query_df("SELECT MIN(peer_count) AS mn FROM industry_benchmarks", settings=s).iloc[0]
    assert int(r["mn"]) >= 1


def test_checkout_conversion_uses_sessions():
    n = query_df("SELECT COUNT(*) AS n FROM fct_checkout_conversion", settings=s).iloc[0]["n"]
    assert int(n) > 0


def test_opportunities_table_persisted():
    tables = set(list_tables(s))
    assert "opportunities_final" in tables
    n = query_df("SELECT COUNT(*) AS n FROM opportunities_final", settings=s).iloc[0]["n"]
    assert int(n) > 0


def test_hyper_extract_exists():
    if not s.hyper_path.exists():
        pytest.skip("Hyper extract not built; run `make build-hyper`")
    assert s.hyper_path.stat().st_size > 10_000


def test_api_health_and_metrics():
    from fastapi.testclient import TestClient
    from src.api.main import app
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    r = c.get("/metrics/overview")
    assert r.status_code == 200
    kpis = {k["metric"]: k["value"] for k in r.json()["kpis"]}
    assert kpis["success_rate"] is not None
    assert 0 < kpis["success_rate"] <= 100
    assert kpis["tpv"] > 0


def test_api_merchant_and_benchmark_endpoints():
    from fastapi.testclient import TestClient
    from src.api.main import app
    c = TestClient(app)
    r = c.get("/metrics/merchant/M0013")
    assert r.status_code == 200
    assert r.json()["merchant_name"] == "Nova Fashion"
    r = c.get("/benchmarks/merchant/M0013")
    assert r.status_code == 200
    assert r.json()["benchmark_status"] in ("VALID", "INSUFFICIENT_SAMPLE", "NO_PEERS")


def test_api_opportunities_list_and_detail():
    from fastapi.testclient import TestClient
    from src.api.main import app
    c = TestClient(app)
    r = c.get("/opportunities")
    assert r.status_code == 200
    j = r.json()
    assert j["count"] > 0
    oid = j["opportunities"][0]["opportunity_id"]
    r2 = c.get(f"/opportunities/{oid}")
    assert r2.status_code == 200
    assert r2.json()["opportunity_id"] == oid


def test_api_404_for_unknown_merchant():
    from fastapi.testclient import TestClient
    from src.api.main import app
    c = TestClient(app)
    # unknown merchant in a window with no data -> 404
    r = c.get("/metrics/merchant/ZZZZ?start_date=2000-01-01&end_date=2000-01-02")
    assert r.status_code == 404
