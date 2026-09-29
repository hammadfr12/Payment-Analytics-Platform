-- staging/stg_checkout_events.sql
-- Clean projection of checkout funnel events.
-- The four event types: checkout_started, payment_attempted, payment_success, payment_failed.

CREATE OR REPLACE TABLE stg_checkout_events AS
SELECT
    CAST(event_id AS VARCHAR)            AS event_id,
    CAST(checkout_session_id AS VARCHAR) AS checkout_session_id,
    CAST(merchant_id AS VARCHAR)         AS merchant_id,
    CAST(event_timestamp AS TIMESTAMP)   AS event_timestamp,
    CAST(event_type AS VARCHAR)          AS event_type,
    CAST(device AS VARCHAR)              AS device,
    CAST(platform AS VARCHAR)            AS platform,
    CAST(payment_method AS VARCHAR)      AS payment_method,
    CAST(event_timestamp AS DATE)        AS event_date
FROM raw_checkout_events;
