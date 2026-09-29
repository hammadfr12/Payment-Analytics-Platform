# Data Dictionary

## `raw_payment_transactions` / `fct_payment_performance`

| field | type | description | nullable | example |
|---|---|---|---|---|
| transaction_id | VARCHAR | unique transaction identifier | no | T_M0013_5_12 |
| merchant_id | VARCHAR | merchant foreign key | no | M0013 |
| event_timestamp | TIMESTAMP | when the attempt occurred | no | 2026-09-20 14:03:00 |
| amount | DOUBLE | transaction amount (INR) | no | 1299.00 |
| currency | VARCHAR | ISO currency | no | INR |
| payment_method | VARCHAR | UPI / Credit Card / Debit Card / Netbanking / Wallet | no | UPI |
| payment_type | VARCHAR | OneTime / EMI / Recurring / Saved | no | OneTime |
| card_type | VARCHAR | Credit / Debit / Prepaid | yes | Debit |
| issuer_bank | VARCHAR | card issuer / bank | yes | HDFC |
| industry | VARCHAR | merchant industry | no | E-commerce |
| mcc | VARCHAR | merchant category code | no | 5651 |
| device | VARCHAR | Mobile / Desktop / Tablet | no | Mobile |
| platform | VARCHAR | Android / iOS / Web | no | Android |
| country | VARCHAR | transaction country | no | IN |
| status | VARCHAR | authorized / failed | no | authorized |
| error_code | VARCHAR | error code on failure | yes | E002 |
| authorized_at | TIMESTAMP | authorization time (success only) | yes | 2026-09-20 14:03:07 |
| checkout_session_id | VARCHAR | originating checkout session | no | S_M0013_5_12 |
| is_eligible | BOOLEAN | amount present and > 0 | no | true |
| is_authorized | BOOLEAN | authorized_at IS NOT NULL | no | true |
| is_failed | BOOLEAN | eligible and not authorized | no | false |

## `raw_merchants` / `stg_merchants`

| field | type | description | nullable | example |
|---|---|---|---|---|
| merchant_id | VARCHAR | merchant key | no | M0013 |
| merchant_name | VARCHAR | display name | no | Nova Fashion |
| industry | VARCHAR | industry | no | E-commerce |
| mcc | VARCHAR | category code | no | 5651 |
| merchant_segment | VARCHAR | SMB / Mid-Market / Enterprise | no | Mid-Market |
| account_manager | VARCHAR | owner | no | Aarav Sharma |
| country | VARCHAR | merchant country | no | IN |
| onboarded_at | TIMESTAMP | onboarding date | no | 2024-03-11 |

## `raw_checkout_events` / `stg_checkout_events` / `fct_checkout_conversion`

| field | type | description | nullable | example |
|---|---|---|---|---|
| event_id | VARCHAR | event key | no | E000000123 |
| checkout_session_id | VARCHAR | session key | no | S_M0013_5_12 |
| merchant_id | VARCHAR | merchant key | no | M0013 |
| event_timestamp | TIMESTAMP | event time | no | 2026-09-20 14:03:00 |
| event_type | VARCHAR | checkout_started / payment_attempted / payment_success / payment_failed | no | payment_success |
| device | VARCHAR | device | no | Mobile |
| platform | VARCHAR | platform | no | Android |
| payment_method | VARCHAR | method | no | UPI |
| started / attempted / success / failed | BOOLEAN | session outcome flags (conversion fact) | no | true |

## `dim_error_codes`

| field | type | description | nullable | example |
|---|---|---|---|---|
| error_code | VARCHAR | code | no | E001 |
| error_category | VARCHAR | Issuer Decline / Network / Authentication / Risk Block / System / User Drop-off | no | Issuer Decline |
| description | VARCHAR | human description | no | Do not honour |
| owner_team | VARCHAR | owning team | no | Issuer |

## `dim_payment_methods`

| field | type | description | nullable | example |
|---|---|---|---|---|
| payment_method | VARCHAR | method | no | UPI |
| payment_type | VARCHAR | type | no | OneTime |
| card_type | VARCHAR | card type (cards only) | yes | Debit |

## `dim_calendar`

| field | type | description | nullable | example |
|---|---|---|---|---|
| date | DATE | calendar date | no | 2026-09-20 |
| week_start | DATE | Monday of the week | no | 2026-09-14 |
| month_start | DATE | first of month | no | 2026-09-01 |
| quarter | INT | quarter | no | 3 |
| year | INT | year | no | 2026 |

## Analytical tables

| table | grain | key columns |
|---|---|---|
| merchant_daily_metrics | merchant × date | success_rate, failure_rate, aov, tpv, counts |
| merchant_weekly_metrics | merchant × week | same, weekly |
| industry_benchmarks | industry × country × method | benchmark_sr, peer_count, txn_count |
| payment_method_metrics | merchant × method × week | success_rate, tpv |
| rca_metrics | merchant × week × segment | segment_sr, counts |
| opportunity_candidates | merchant × week | success_rate, sr_delta_pp |
| opportunities_final | opportunity | full opportunity schema |
