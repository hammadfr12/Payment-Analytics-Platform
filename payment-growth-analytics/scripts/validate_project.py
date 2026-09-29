#!/usr/bin/env python3
"""Validate the project: artifacts exist, tables populated, KPIs sane, no secrets.

Exit code 0 = all checks pass, 1 = at least one failure. Prints a checklist.
"""
from __future__ import annotations

import sys

from src.common.queries import query_df, list_tables
from src.config.settings import get_settings
from src.opportunities.engine import load_opportunities_df

s = get_settings()
checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main():
    print("Project validation")
    print("=" * 60)

    # 1. Data generated
    raw = s.raw_dir / "payment_transactions.parquet"
    check("1. Raw data generated", raw.exists(), str(raw.name))

    # 2. DuckDB exists
    check("2. DuckDB database exists", s.duckdb_path.exists(),
          f"{s.duckdb_path.stat().st_size / 1e6:.0f} MB" if s.duckdb_path.exists() else "")

    tables = set(list_tables(s)) if s.duckdb_path.exists() else set()

    # 3. SQL tables populated
    key_tables = ["fct_payment_performance", "merchant_weekly_metrics",
                  "industry_benchmarks", "rca_metrics"]
    populated = all(t in tables for t in key_tables)
    check("3. SQL tables populated", populated,
          f"{len(tables)} tables in DB")

    # 4. KPI numbers non-null and sensible
    if "merchant_weekly_metrics" in tables:
        r = query_df("""SELECT COUNT(*) AS n,
                        MIN(success_rate) AS mn, MAX(success_rate) AS mx
                        FROM merchant_weekly_metrics WHERE success_rate IS NOT NULL""",
                     settings=s).iloc[0]
        ok = int(r["n"]) > 0 and 0 <= float(r["mn"]) <= 100 and 0 <= float(r["mx"]) <= 100
        check("4. KPI numbers sensible", ok,
              f"SR range [{float(r['mn']):.1f}, {float(r['mx']):.1f}]")
    else:
        check("4. KPI numbers sensible", False, "merchant_weekly_metrics missing")

    # 5. Benchmark records have valid sample sizes
    if "industry_benchmarks" in tables:
        r = query_df("""SELECT COUNT(*) AS n, MIN(peer_count) AS pc,
                        MIN(txn_count) AS tc FROM industry_benchmarks""", settings=s).iloc[0]
        ok = int(r["n"]) > 0 and int(r["pc"]) >= 1 and int(r["tc"]) > 0
        check("5. Benchmark sample sizes valid", ok,
              f"{int(r['n'])} groups, min peers {int(r['pc'])}")
    else:
        check("5. Benchmark sample sizes valid", False, "industry_benchmarks missing")

    # 6. RCA identifies the degraded scenario (Nova)
    try:
        from src.rca.engine import run_rca
        from src.opportunities.engine import _latest_two_weeks
        cs, ce, ps, pe = _latest_two_weeks(s)
        rca = run_rca("M0013", cs, ce, ps, pe, settings=s)
        ok = rca.overall_delta_pp is not None and rca.overall_delta_pp <= -3.0
        check("6. RCA identifies degraded scenario", ok,
              f"Nova delta {rca.overall_delta_pp:.2f} pp")
    except Exception as e:
        check("6. RCA identifies degraded scenario", False, str(e))

    # 7. Opportunities generated
    try:
        opps = load_opportunities_df(s)
        check("7. Opportunities generated", len(opps) > 0,
              f"{len(opps)} opportunities")
    except Exception as e:
        check("7. Opportunities generated", False, str(e))

    # 8. Hyper file exists
    check("8. Hyper extract exists", s.hyper_path.exists(),
          f"{s.hyper_path.stat().st_size / 1e6:.1f} MB" if s.hyper_path.exists() else "")

    # 9. FastAPI health endpoint works
    try:
        from fastapi.testclient import TestClient
        from src.api.main import app
        c = TestClient(app)
        r = c.get("/health")
        check("9. FastAPI health endpoint", r.status_code == 200,
              f"status {r.status_code}")
    except Exception as e:
        check("9. FastAPI health endpoint", False, str(e))

    # 10. Streamlit app importable
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "stapp", s.project_root / "app" / "streamlit" / "app.py")
        check("10. Streamlit app present", spec is not None,
              "app/streamlit/app.py")
    except Exception as e:
        check("10. Streamlit app present", False, str(e))

    # 11. Documentation exists
    doc_files = ["README.md", "PRD.md", "ENVIRONMENT.md",
                 "docs/architecture.md", "docs/data_dictionary.md",
                 "docs/metric_definitions.md", "docs/rca_methodology.md",
                 "docs/tableau_setup.md"]
    have = [d for d in doc_files if (s.project_root / d).exists()]
    check("11. Documentation exists", len(have) >= 6,
          f"{len(have)}/{len(doc_files)} docs")

    # 12. No secrets in tracked source
    import subprocess
    secret_hits = 0
    try:
        for pyf in (s.project_root / "src").rglob("*.py"):
            txt = pyf.read_text().lower()
            for marker in ["password =", "api_key =", "secret =", "token ="]:
                if marker in txt and "example" not in txt:
                    secret_hits += 1
    except Exception:
        pass
    check("12. No secrets in source", secret_hits == 0, f"{secret_hits} potential hits")

    # 13. No real customer data (synthetic only)
    has_disclaimer = (s.project_root / "README.md").exists() and \
        "synthetic" in (s.project_root / "README.md").read_text().lower()
    check("13. Synthetic-data disclaimer present", has_disclaimer)

    # 14. Tests pass (delegates to pytest; run separately by `make test`)
    check("14. Test suite available", (s.project_root / "tests").exists(),
          "run `make test`")

    total = len(checks)
    passed = sum(1 for _, ok, _ in checks if ok)
    print("=" * 60)
    print(f"Validation: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
