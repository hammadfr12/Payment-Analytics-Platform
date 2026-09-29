# Tableau Setup

This document provides **exact steps** to connect the generated Hyper extract to
Tableau Desktop and build the five dashboards.

> **Validation status.** Tableau Desktop **2026.2 is installed** on the build
> machine, so the extract is openable. The `.twb` workbook shipped here is
> validated **structurally** (well-formed XML; the five dashboards and their
> sheets are present). It has **not** been visually opened/verified in this
> build. Do not describe the workbook as "visually validated" until a person
> opens it in Tableau Desktop.

## Artifacts

| Artifact | Path |
|---|---|
| Hyper extract (7 datasets) | `tableau/extracts/payment_growth.hyper` |
| Workbook (5 dashboards) | `tableau/workbooks/payment_growth.twb` |
| Datasource definition | `tableau/datasource/payment_growth.tds` |

Rebuild the extract any time with:

```bash
make build-hyper
```

## Datasets inside the extract

| Table name | Source | Grain |
|---|---|---|
| `merchant_performance` | merchant_weekly_metrics | merchant × week |
| `industry_benchmark` | industry_benchmarks | industry × country × method |
| `rca` | rca_metrics | merchant × week × segment |
| `opportunities` | opportunities_final | opportunity |
| `checkout_conversion` | fct_checkout_conversion (aggregated) | merchant × week |
| `payment_method_metrics` | payment_method_metrics | merchant × method × week |
| `merchants` | stg_merchants | merchant |
| `_extract_metadata` | row counts | dataset |

## Connect the Hyper file

1. Open Tableau Desktop → **Connect → To a file → More…**
2. Select `tableau/extracts/payment_growth.hyper`.
3. Tableau lists the tables above. Drag **`merchant_performance`** onto the
   canvas.
4. Add `merchants` and join on `merchant_id` (or relate — the tables are a
   star schema around `merchant_id` and `week_start`).
5. Repeat for the other datasets, or drag further tables to blend.
6. Set `week_start` as a **Date** dimension (`week_start` is a DATE column).

## Calculated fields

Prefer precomputed SQL metrics for complex logic. The workbook already defines
these; recreate them if you build a fresh datasource:

| Field | Formula | Notes |
|---|---|---|
| `SR %` | `[success_rate]` | precomputed in SQL |
| `AOV` | `IF [authorized_count] > 0 THEN [successful_tpv] / [authorized_count] END` | protected |
| `Failure Rate %` | `[failure_rate]` | precomputed |
| `SR Delta pp` | `[success_rate] - LOOKUP([success_rate], -1)` | table calc, week grain |
| `SR WoW %` | `(ZN([success_rate]) - LOOKUP([success_rate], -1)) / ABS(LOOKUP([success_rate], -1)) * 100` | table calc |
| `Benchmark Gap pp` | `[success_rate] - [benchmark_sr]` | after relating benchmark |
| `Payment Method Share %` | `SUM([tpv]) / TOTAL(SUM([tpv])) * 100` | table calc |

## Dashboards

### 1. Executive Overview
- **Filters:** Date range (parameter), Merchant, Industry, MCC, Payment method, Country, Device, Platform
- **KPI cards:** SR %, TPV, Transactions, AOV, Checkout Conversion, Failure Rate
- **Charts:** SR trend (line by week), TPV trend (line), payment-method mix (pie),
  merchant vs benchmark (scatter), top opportunities (bar), opportunity table

### 2. Merchant Performance
- Merchant KPIs, SR trend, payment-method table (SR + share), device/platform breakdown

### 3. Industry Benchmarking
- Industry SR, merchant SR, peer count, transaction volume, benchmark gap,
  distribution/percentile where sample permits

### 4. RCA Explorer
- Interactive hierarchy: Overall SR → Payment Method → Card Type → Issuer;
  Device → Platform; Error Category. Current vs previous period + contribution bar.

### 5. Opportunity Center
- Opportunity cards table (merchant, type, severity, metric movement, gap,
  evidence, next step), filters by severity/type/industry

## Filters, actions, tooltips

- **Dashboard filters:** date range via a parameter + calculated filter; categorical
  filters wired across all sheets.
- **Dashboard actions:** "Use as Filter" from the payment-method bar to the RCA
  drill-down sheets; highlight action from opportunities to merchant trend.
- **Tooltips:** attach metric definitions — SR = authorized/eligible × 100;
  Gap = merchant − benchmark; Contribution = previous-volume-share × rate movement.
- **Sample-size warnings:** show `peer_count` and `sample_txn_count` on the
  Benchmarking dashboard; grey out / annotate rows where `benchmark_status ≠ VALID`.

## Documented DuckDB/Trino differences

The extract is built from DuckDB results. The SQL models are Trino-compatible;
where syntax differs from Trino the `.sql` files carry a note. No Tableau
calculation depends on DuckDB-specific behaviour — Tableau only receives
precomputed columns and applies lightweight presentation maths.

## What remains manual

1. Open `payment_growth.twb` / the Hyper file in Tableau Desktop.
2. Confirm field types (dates, measures) and formatting.
3. Position sheets on each dashboard and wire filters/actions (steps above).
4. Visually verify each dashboard — this is the step the build could not do.
