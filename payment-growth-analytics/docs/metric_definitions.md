# Metric Definitions

Single source of truth: `src/analytics/metrics.py`. Every KPI below is unit-tested
in `tests/unit/test_metrics.py`.

---

## Success Rate (SR)

| Field | Value |
|---|---|
| Definition | authorized eligible transactions / eligible transactions × 100 |
| Numerator | count of eligible transactions where `authorized_at IS NOT NULL` |
| Denominator | count of eligible transactions (`amount IS NOT NULL AND amount > 0`) |
| Grain | any (merchant, day, week, segment) |
| Filters | date, merchant, industry, method, device, platform, country |
| Edge cases | denominator = 0 → `NULL` (never 0 or NaN); never exceeds 100 |

## TPV (Total Payment Value)

| Field | Value |
|---|---|
| Definition | `SUM(amount)` over eligible transactions |
| Numerator | n/a |
| Denominator | n/a |
| Grain | any |
| Edge cases | empty selection → 0 |

## Transaction Count

| Field | Value |
|---|---|
| Definition | `COUNT(DISTINCT transaction_id)` |
| Edge cases | duplicates never inflate the count |

## AOV (Average Order Value)

| Field | Value |
|---|---|
| Definition | successful TPV / successful transaction count |
| Numerator | `SUM(amount)` where authorized |
| Denominator | count where authorized |
| Edge cases | denominator = 0 → `NULL` |
| Note | uses **successful** count, not eligible |

## Failure Rate

| Field | Value |
|---|---|
| Definition | failed eligible transactions / eligible transactions × 100 |
| Numerator | eligible transactions that are not authorized |
| Denominator | eligible transactions |
| Edge cases | denominator = 0 → `NULL` |

## Payment Method Share

| Field | Value |
|---|---|
| Definition | method TPV / total TPV × 100 |
| Denominator | total TPV across all methods for the same scope |
| Edge cases | total = 0 → `NULL` |

## Checkout Conversion

| Field | Value |
|---|---|
| Definition | sessions with a `payment_success` event / sessions with a `checkout_started` event × 100 |
| Source | **checkout_events table**, never derived from transactions |
| Grain | checkout_session_id |
| Edge cases | started sessions = 0 → `NULL` |

## Percentage-point delta (for rates)

`current_rate − previous_rate`. Never labelled "percentage change".

## Percentage delta (for absolute metrics)

`(current − previous) / previous × 100`. Returns `NULL` where previous = 0.

---

## Benchmark metrics

| Metric | Definition |
|---|---|
| merchant_sr | target merchant's SR in the window |
| benchmark_sr | **weighted** aggregate SR of the peer group |
| gap_pp | `merchant_sr − benchmark_sr` (percentage points) |
| peer_count | distinct merchants in the peer group (excluding self) |
| sample_txn_count | eligible transactions in the peer group |
| benchmark_status | `VALID` / `INSUFFICIENT_SAMPLE` / `NO_PEERS` |

Peer group = **industry + country + payment_method + date range**.

## RCA metrics

| Metric | Definition |
|---|---|
| current_sr / previous_sr | segment SR in each period |
| delta_pp | `current_sr − previous_sr` |
| contribution | `previous_volume_share × delta_pp` |
| share_of_decline | `abs(contribution) / Σ abs(contributions)` within the dimension |
| volume_current / volume_previous | eligible transactions per segment per period |

## Opportunity fields

See [README § Opportunity engine](../README.md#opportunity-engine) and
`src/opportunities/engine.py`. `confidence` = evidence quality (High/Medium/Low),
not causal certainty.
