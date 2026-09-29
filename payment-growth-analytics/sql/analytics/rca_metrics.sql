-- analytics/rca_metrics.sql
-- RCA prep table: per-merchant, per-dimension-value, current vs previous week.
-- Contribution decomposition is finalized in Python (src/rca/engine.py) because
-- it mixes volume-weight and rate-movement logic that is clearer in pandas.
-- This SQL provides the segment-level current/previous aggregates.

CREATE OR REPLACE TABLE rca_metrics AS
WITH weekly_segment AS (
    SELECT
        merchant_id,
        merchant_name,
        industry,
        week_start,
        payment_method,
        card_type,
        issuer_bank,
        device,
        platform,
        error_code,
        COUNT(DISTINCT transaction_id)                                       AS txn_count,
        SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END)                       AS eligible_count,
        SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END)                       AS authorized_count
    FROM fct_payment_performance
    WHERE is_eligible = TRUE
    GROUP BY merchant_id, merchant_name, industry, week_start,
             payment_method, card_type, issuer_bank, device, platform, error_code
)
SELECT
    merchant_id,
    merchant_name,
    industry,
    week_start,
    payment_method,
    card_type,
    issuer_bank,
    device,
    platform,
    error_code,
    txn_count,
    eligible_count,
    authorized_count,
    CASE WHEN eligible_count > 0
         THEN 100.0 * authorized_count / NULLIF(eligible_count, 0)
         ELSE NULL END AS segment_sr
FROM weekly_segment;
