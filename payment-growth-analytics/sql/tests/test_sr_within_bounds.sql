-- sql/tests/test_sr_within_bounds.sql
-- Smoke test: SR must be between 0 and 100 for every merchant-week.

SELECT COUNT(*) AS violations
FROM merchant_weekly_metrics
WHERE success_rate IS NOT NULL
  AND (success_rate < 0 OR success_rate > 100);
-- expected: 0
