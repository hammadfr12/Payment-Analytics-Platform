-- analytics/payment_method_metrics.sql
-- Payment-method level metrics across the whole dataset and per merchant/week.
-- Two grains are useful; this file builds the merchant x week x method grain.

CREATE OR REPLACE TABLE payment_method_metrics AS
SELECT
    merchant_id,
    merchant_name,
    industry,
    payment_method,
    week_start,
    COUNT(DISTINCT transaction_id)                                        AS transaction_count,
    SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END)                       AS eligible_count,
    SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END)                       AS authorized_count,
    SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END)                  AS tpv,
    CASE WHEN SUM(CASE WHEN is_eligible THEN 1 ELSE 0 END) > 0
         THEN 100.0 * SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN is_eligible THEN 1 ELSE 0 END), 0)
         ELSE NULL END                                                    AS success_rate,
    -- Share of TPV (relative to all methods for this merchant/week) computed downstream
    NULL                                                                  AS tpv_share_pct
FROM fct_payment_performance
WHERE is_eligible = TRUE
GROUP BY merchant_id, merchant_name, industry, payment_method, week_start;
