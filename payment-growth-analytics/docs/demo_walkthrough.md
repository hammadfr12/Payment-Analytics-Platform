# Demo Walkthrough

A scripted narrative around one synthetic merchant that shows this is a
**decision-support product**, not just a dashboard.

## Setup

```bash
make demo          # generate → load → SQL → analytics → opportunities
make run-app       # Streamlit on http://127.0.0.1:8501
```

## The narrative

```
Merchant performance dropped
        ↓
SR declined ~5.6 pp (WoW)
        ↓
Merchant is ~3.6 pp below its industry benchmark
        ↓
RCA identifies a concentrated movement
        ↓
Android + Debit Card is a major contributor
        ↓
Issuer (HDFC) and Issuer-Decline error pattern are elevated
        ↓
An opportunity is created (Critical)
        ↓
A recommended next investigation is displayed
```

## Steps in the app

1. **Overview** — the KPI row shows portfolio SR ~95.3%, TPV ~₹371 Cr, 1.16M
   transactions, AOV ~₹3,201, checkout conversion ~95.3%, failure rate ~4.7%.
   The trend chart shows a visible dip in the final week; the top-opportunities
   table surfaces Nova Fashion.

2. **Merchant Performance** — select **Nova Fashion (M0013)**. Its SR trend shows
   the drop in the final two weeks. The payment-method table shows **Debit Card**
   with the lowest SR; the device/platform chart shows **Android** lagging.

3. **Benchmarking** — Nova sits **below** the E-commerce benchmark line; the gap
   card shows a negative value and the peer/sample counts confirm the comparison
   is `VALID`.

4. **RCA Explorer** — select Nova. Previous SR → current SR with a negative delta.
   The contribution chart ranks contributors; **Android** and **Debit Card**
   appear prominently, with **Issuer Decline** elevated among error categories.

5. **Opportunity Center** — filter to **Critical**. Nova Fashion carries a
   `RULE_SR_DECLINE` and a `RULE_BENCHMARK_GAP` opportunity, each with supporting
   evidence and a recommended next step: *investigate issuer/error-category
   performance for the Android debit-card segment.*

6. **Data Quality** — record counts and zero violation counts confirm the
   pipeline is healthy.

## Via the API

```bash
curl http://127.0.0.1:8000/metrics/merchant/M0013
curl "http://127.0.0.1:8000/metrics/rca?merchant_id=M0013"
curl http://127.0.0.1:8000/benchmarks/merchant/M0013
curl "http://127.0.0.1:8000/opportunities?severity=Critical"
```

## The product promise

> From **"What changed?"** → **"Why did it change?"** → **"What should we investigate next?"**

Every step above is derived from the synthetic transactions via documented SQL
and Python — no value is entered by hand.
