-- marts/fct_checkout_conversion.sql
-- Checkout conversion fact at session grain.
-- Denominator: checkout sessions STARTED. Numerator: sessions with payment_success.
-- IMPORTANT: conversion is derived from checkout_events, NOT from transactions.

CREATE OR REPLACE TABLE fct_checkout_conversion AS
WITH session_outcomes AS (
    SELECT
        checkout_session_id,
        merchant_id,
        MIN(event_date)  AS session_date,
        -- session started flag
        CAST(SUM(CASE WHEN event_type = 'checkout_started'   THEN 1 ELSE 0 END) > 0 AS BOOLEAN) AS started,
        CAST(SUM(CASE WHEN event_type = 'payment_attempted'  THEN 1 ELSE 0 END) > 0 AS BOOLEAN) AS attempted,
        CAST(SUM(CASE WHEN event_type = 'payment_success'    THEN 1 ELSE 0 END) > 0 AS BOOLEAN) AS success,
        CAST(SUM(CASE WHEN event_type = 'payment_failed'     THEN 1 ELSE 0 END) > 0 AS BOOLEAN) AS failed,
        ANY_VALUE(device)         AS device,
        ANY_VALUE(platform)       AS platform,
        ANY_VALUE(payment_method) AS payment_method
    FROM stg_checkout_events
    GROUP BY checkout_session_id, merchant_id
)
SELECT
    checkout_session_id,
    merchant_id,
    session_date,
    CAST(session_date - CAST((EXTRACT(dow FROM session_date)) AS INTEGER) AS DATE) AS week_start,
    date_trunc('month', session_date) AS month_start,
    started,
    attempted,
    success,
    failed,
    device,
    platform,
    payment_method
FROM session_outcomes
WHERE started = TRUE;
