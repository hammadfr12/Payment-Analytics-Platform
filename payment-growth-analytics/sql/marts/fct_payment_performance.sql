-- marts/fct_payment_performance.sql
-- Payment performance fact at transaction grain with KPI-ready flags.
-- Joins to merchants for analyst-friendly labels (explicit column list).

CREATE OR REPLACE TABLE fct_payment_performance AS
SELECT
    t.transaction_id,
    t.merchant_id,
    m.merchant_name,
    m.industry,
    m.mcc,
    m.merchant_segment,
    m.account_manager,
    m.country             AS merchant_country,
    t.event_timestamp,
    t.event_date,
    CAST(t.event_date - CAST((EXTRACT(dow FROM t.event_date)) AS INTEGER) AS DATE) AS week_start,
    date_trunc('month', t.event_date) AS month_start,
    t.amount,
    t.currency,
    t.payment_method,
    t.payment_type,
    t.card_type,
    t.issuer_bank,
    t.device,
    t.platform,
    t.country             AS txn_country,
    t.status,
    t.error_code,
    t.authorized_at,
    t.checkout_session_id,
    t.is_eligible,
    t.is_authorized,
    t.is_failed
FROM stg_transactions t
LEFT JOIN stg_merchants m
    ON t.merchant_id = m.merchant_id;
