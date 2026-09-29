-- analytics/merchant_daily_metrics.sql
-- Daily KPI rollup per merchant.
-- Denominators protected with NULLIF.

CREATE OR REPLACE TABLE merchant_daily_metrics AS
SELECT
    merchant_id,
    merchant_name,
    industry,
    mcc,
    merchant_country AS country,
    event_date,
    week_start,
    month_start,
    COUNT(DISTINCT transaction_id)                                       AS transaction_count,
    SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END)                       AS eligible_count,
    SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END)                       AS authorized_count,
    SUM(CASE WHEN is_failed     THEN 1 ELSE 0 END)                       AS failed_count,
    SUM(CASE WHEN is_eligible   THEN amount ELSE 0 END)                  AS tpv,
    SUM(CASE WHEN is_authorized THEN amount ELSE 0 END)                  AS successful_tpv,
    -- SR% = authorized / eligible * 100
    CASE WHEN SUM(CASE WHEN is_eligible THEN 1 ELSE 0 END) > 0
         THEN 100.0 * SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN is_eligible THEN 1 ELSE 0 END), 0)
         ELSE NULL END                                                   AS success_rate,
    -- Failure rate%
    CASE WHEN SUM(CASE WHEN is_eligible THEN 1 ELSE 0 END) > 0
         THEN 100.0 * SUM(CASE WHEN is_failed THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN is_eligible THEN 1 ELSE 0 END), 0)
         ELSE NULL END                                                   AS failure_rate,
    -- AOV = successful TPV / successful txn count
    CASE WHEN SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END) > 0
         THEN SUM(CASE WHEN is_authorized THEN amount ELSE 0 END)
              / NULLIF(SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END), 0)
         ELSE NULL END                                                   AS aov
FROM fct_payment_performance
WHERE is_eligible = TRUE
GROUP BY merchant_id, merchant_name, industry, mcc, merchant_country,
         event_date, week_start, month_start;
