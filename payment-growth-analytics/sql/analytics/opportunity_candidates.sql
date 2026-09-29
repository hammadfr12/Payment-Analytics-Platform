-- analytics/opportunity_candidates.sql
-- Candidate seed table for the opportunity engine: merchant x week with
-- current vs previous SR and benchmark gap. The Python opportunity engine
-- (src/opportunities/engine.py) applies the rules and writes the final
-- opportunity table.

CREATE OR REPLACE TABLE opportunity_candidates AS
WITH weekly AS (
    SELECT
        merchant_id,
        merchant_name,
        industry,
        country,
        week_start,
        eligible_count,
        authorized_count,
        tpv,
        successful_tpv,
        CASE WHEN eligible_count > 0
             THEN 100.0 * authorized_count / NULLIF(eligible_count, 0)
             ELSE NULL END AS success_rate
    FROM merchant_weekly_metrics
),
ranked AS (
    SELECT
        w.*,
        LAG(success_rate)   OVER (PARTITION BY merchant_id ORDER BY week_start) AS prev_success_rate,
        LAG(eligible_count) OVER (PARTITION BY merchant_id ORDER BY week_start) AS prev_eligible_count
    FROM weekly w
)
SELECT
    merchant_id,
    merchant_name,
    industry,
    country,
    week_start,
    eligible_count,
    authorized_count,
    tpv,
    successful_tpv,
    success_rate,
    prev_success_rate,
    prev_eligible_count,
    -- SR delta in percentage points (current - previous)
    (success_rate - prev_success_rate) AS sr_delta_pp,
    -- absolute volume change
    (eligible_count - prev_eligible_count) AS volume_delta
FROM ranked
WHERE prev_success_rate IS NOT NULL;
