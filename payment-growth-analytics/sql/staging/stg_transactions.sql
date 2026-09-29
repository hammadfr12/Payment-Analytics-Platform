-- staging/stg_transactions.sql
-- Clean, typed projection of raw payment transactions.
-- Trino-compatible: explicit casts, no SELECT *, eligible/successful flags.
-- DuckDB adaptation: DuckDB supports all functions used here (CAST, COALESCE,
-- date_trunc, EXTRACT). Trino would use date_trunc('day', x) identically.

CREATE OR REPLACE TABLE stg_transactions AS
SELECT
    CAST(transaction_id AS VARCHAR)        AS transaction_id,
    CAST(merchant_id AS VARCHAR)           AS merchant_id,
    CAST(event_timestamp AS TIMESTAMP)     AS event_timestamp,
    CAST(amount AS DOUBLE)                 AS amount,
    CAST(currency AS VARCHAR)              AS currency,
    CAST(payment_method AS VARCHAR)        AS payment_method,
    CAST(payment_type AS VARCHAR)          AS payment_type,
    CAST(card_type AS VARCHAR)             AS card_type,
    CAST(issuer_bank AS VARCHAR)           AS issuer_bank,
    CAST(industry AS VARCHAR)              AS industry,
    CAST(mcc AS VARCHAR)                   AS mcc,
    CAST(device AS VARCHAR)                AS device,
    CAST(platform AS VARCHAR)              AS platform,
    CAST(country AS VARCHAR)               AS country,
    CAST(status AS VARCHAR)                AS status,
    CAST(error_code AS VARCHAR)            AS error_code,
    CAST(authorized_at AS TIMESTAMP)       AS authorized_at,
    CAST(checkout_session_id AS VARCHAR)   AS checkout_session_id,
    CAST(event_timestamp AS DATE)          AS event_date,
    -- Eligible: every attempt that reached the gateway (exclude null amounts).
    CAST(amount IS NOT NULL AND amount > 0 AS BOOLEAN) AS is_eligible,
    -- Successful/authorized: per PRD, authorized_at IS NOT NULL.
    CAST(authorized_at IS NOT NULL AS BOOLEAN)          AS is_authorized,
    -- Failed: eligible and not authorized.
    CAST((amount IS NOT NULL AND amount > 0 AND authorized_at IS NULL) AS BOOLEAN) AS is_failed
FROM raw_payment_transactions;
