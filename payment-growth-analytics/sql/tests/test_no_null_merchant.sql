-- sql/tests/test_no_null_merchant.sql
-- Smoke test: no transaction may have a null merchant_id.

SELECT COUNT(*) AS violations
FROM fct_payment_performance
WHERE merchant_id IS NULL;
-- expected: 0
