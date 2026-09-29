# Build Report — Payment Growth Analytics Platform

**Status: COMPLETE** — validation and tests executed and passing on the build machine.

---

## Environment

| Item | Value |
|---|---|
| OS | macOS (Darwin 25.6.0, arm64) |
| Python | 3.9.6 (system `/usr/bin/python3`) — PRD prefers 3.11+; 3.9-compatible code |
| Package manager | `venv` + `pip` (no `uv`/`poetry`/`conda` present) |
| DuckDB | 1.4.5 (embedded in-process) |
| Tableau Desktop | 2026.2 (Apple silicon) — installed |
| Tableau Hyper API | 0.0.26479 |
| Java | not installed (not required) |
| Docker | not installed (`docker-compose.yml` provided for reference) |
| Node | v26.3.0 (unused) |
| Git | 2.50.1 |

Full detail in `ENVIRONMENT.md`.

## Files created

- **Python:** 45 files across `src/`, `app/`, `scripts/`, `tests/`
- **SQL:** 15 files (`sql/staging`, `sql/marts`, `sql/analytics`, `sql/tests`)
- **Docs:** README, PRD, ENVIRONMENT, BUILD_REPORT, LICENSE + 6 files in `docs/`
- **Config:** `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`, `Makefile`, `docker-compose.yml`
- **Tableau:** `.hyper` extract, `.twb` workbook, `.tds` datasource, setup documentation

## Commands executed

```bash
make setup            # venv + editable install
python scripts/generate_data.py   # 1,155,150 transactions; 3,465,450 checkout events
python scripts/load_data.py       # 6 raw/dim tables into DuckDB
python scripts/run_sql.py         # 11 SQL models
python scripts/run_pipeline.py    # + benchmarks, RCA, opportunities
python scripts/build_hyper.py     # Tableau extract (7 datasets)
python -m pytest                  # 75 tests
python scripts/validate_project.py  # 14/14 checks
```

## Tests passed

```
75 passed in ~35s
```

| Suite | File | Tests |
|---|---|---|
| Unit — metrics | `tests/unit/test_metrics.py` | 20 |
| Unit — benchmark | `tests/unit/test_benchmark.py` | 5 |
| Unit — RCA | `tests/unit/test_rca.py` | 8 |
| Unit — opportunity rules | `tests/unit/test_opportunity_rules.py` | 10 |
| Data quality | `tests/data/test_data_quality.py` | 12 |
| Integration — pipeline + API | `tests/integration/test_pipeline.py` | 12 |
| Integration — regression (S1–S5) | `tests/integration/test_regression_scenarios.py` | 8 |

## Tables created (row counts)

| Table | Rows |
|---|---|
| raw_payment_transactions | 1,155,150 |
| raw_merchants | 150 |
| raw_checkout_events | 3,465,450 |
| fct_payment_performance | 1,155,150 |
| fct_checkout_conversion | 1,155,150 |
| merchant_daily_metrics | 10,500 |
| merchant_weekly_metrics | 1,650 |
| industry_benchmarks | 150 |
| payment_method_metrics | 8,249 |
| rca_metrics | 297,039 |
| opportunity_candidates | 1,500 |
| opportunities_final | 78 |

## API endpoints

`/health` · `/metrics/overview` · `/metrics/merchant/{id}` · `/metrics/industry/{industry}` ·
`/metrics/trend` · `/metrics/payment-method` · `/metrics/rca` · `/benchmarks/merchant/{id}` ·
`/opportunities` · `/opportunities/{id}`

All exercised by integration tests (including a 404 path). OpenAPI docs at `/docs`.

## Tableau artifacts

| Artifact | Path | Status |
|---|---|---|
| Hyper extract | `tableau/extracts/payment_growth.hyper` | built (2.5 MB, 7 datasets + metadata) |
| Workbook | `tableau/workbooks/payment_growth.twb` | generated (5 dashboards, 22 sheets, valid XML) |
| Datasource | `tableau/datasource/payment_growth.tds` | generated |
| Setup guide | `tableau/documentation/tableau_setup.md` | written |

Datasets: `merchant_performance`, `industry_benchmark`, `rca`, `opportunities`,
`checkout_conversion`, `payment_method_metrics`, `merchants`.

## Validation results

```
14/14 checks passed
```

Including: raw data generated · DuckDB exists (300 MB) · SQL tables populated ·
KPI numbers sensible (SR range 87.6–99.2) · benchmark samples valid · **RCA
identifies the degraded scenario (Nova delta −5.58 pp)** · 78 opportunities
generated · Hyper exists · FastAPI health 200 · Streamlit present · 8/8 docs ·
no secrets · synthetic disclaimer present.

## Regression scenarios detected

| # | Scenario | Merchant | Result |
|---|---|---|---|
| S1 | SR decline | M0013 Nova Fashion | detected (−5.58 pp) ✓ |
| S2 | Android + Debit Card | M0013 | Android & Debit Card are major contributors ✓ |
| S3 | Issuer error spike | M0013 / HDFC | HDFC delta −7.37 pp; Issuer Decline elevated ✓ |
| S4 | Benchmark gap | M0042 Budget Grocer | gap −3.23 pp, status VALID ✓ |
| S5 | Strong improvement | M0077 Swift Trips | positive delta; not flagged for decline ✓ |

## Known limitations

- Synthetic data only; results are not real business outcomes.
- Python 3.9.6 (PRD prefers 3.11+) — code avoids 3.10+ syntax.
- Contribution decomposition is a heuristic, not causal inference.
- The Tableau workbook is validated **structurally**, not visually opened; a human
  must open it in Tableau Desktop (available) to confirm layout.
- No auth on API/app (local reference implementation).
- Single-country peer groups can be small; `benchmark_status` flags this.

## Manual Tableau steps remaining

1. Open `tableau/workbooks/payment_growth.twb` (or connect
   `tableau/extracts/payment_growth.hyper` directly).
2. Confirm field types and measures.
3. Position sheets and wire filters/dashboard actions (steps in
   `docs/tableau_setup.md`).
4. Visually verify each of the five dashboards.

---

*All outputs are generated from synthetic data. See the README's synthetic-data
disclaimer.*
