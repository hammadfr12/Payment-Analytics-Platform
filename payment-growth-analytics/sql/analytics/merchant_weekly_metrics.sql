-- analytics/merchant_weekly_metrics.sql
-- Weekly KPI rollup per merchant (grain: merchant x week_start).

CREATE OR REPLACE TABLE merchant_weekly_metrics AS
SELECT
    merchant_id,
    merchant_name,
    industry,
    mcc,
    country,
    week_start,
    SUM(transaction_count)                                                AS transaction_count,
    SUM(eligible_count)                                                   AS eligible_count,
    SUM(authorized_count)                                                 AS authorized_count,
    SUM(failed_count)                                                     AS failed_count,
    SUM(tpv)                                                              AS tpv,
    SUM(successful_tpv)                                                   AS successful_tpv,
    CASE WHEN SUM(eligible_count) > 0
         THEN 100.0 * SUM(authorized_count) / NULLIF(SUM(eligible_count), 0)
         ELSE NULL END                                                    AS success_rate,
    CASE WHEN SUM(eligible_count) > 0
         THEN 100.0 * SUM(failed_count)   / NULLIF(SUM(eligible_count), 0)
         ELSE NULL END                                                    AS failure_rate,
    CASE WHEN SUM(authorized_count) > 0
         THEN SUM(successful_tpv) / NULLIF(SUM(authorized_count), 0)
         ELSE NULL END                                                    AS aov
FROM merchant_daily_metrics
GROUP BY merchant_id, merchant_name, industry, mcc, country, week_start;
