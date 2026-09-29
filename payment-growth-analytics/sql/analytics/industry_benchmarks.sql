-- analytics/industry_benchmarks.sql
-- Industry + country + payment_method benchmark, weighted aggregate SR.
-- Excludes no specific merchant here (peer-exclusion happens at query time);
-- this table is the peer-pool the benchmark engine samples from.
-- benchmark_status computed by the Python benchmark engine, but we also
-- surface peer_count and txn_count for transparency.

CREATE OR REPLACE TABLE industry_benchmarks AS
SELECT
    industry,
    txn_country AS country,
    payment_method,
    COUNT(DISTINCT merchant_id)            AS peer_count,
    COUNT(DISTINCT transaction_id)         AS txn_count,
    SUM(CASE WHEN is_eligible   THEN 1 ELSE 0 END)  AS eligible_count,
    SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END)  AS authorized_count,
    -- Weighted aggregate SR (weighted by eligible volume)
    CASE WHEN SUM(CASE WHEN is_eligible THEN 1 ELSE 0 END) > 0
         THEN 100.0 * SUM(CASE WHEN is_authorized THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN is_eligible THEN 1 ELSE 0 END), 0)
         ELSE NULL END                     AS benchmark_sr,
    SUM(CASE WHEN is_eligible THEN amount ELSE 0 END) AS benchmark_tpv
FROM fct_payment_performance
WHERE is_eligible = TRUE
GROUP BY industry, txn_country, payment_method;
