-- sql/tests/test_positive_amounts.sql
-- Smoke test: eligible transaction amounts must be positive.

SELECT COUNT(*) AS violations
FROM fct_payment_performance
WHERE is_eligible = TRUE AND amount <= 0;
-- expected: 0
