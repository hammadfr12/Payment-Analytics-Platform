-- sql/tests/test_unique_txn.sql
-- Smoke test: transaction_id must be unique.

SELECT transaction_id, COUNT(*) AS n
FROM fct_payment_performance
GROUP BY transaction_id
HAVING COUNT(*) > 1
ORDER BY n DESC
LIMIT 10;
-- expected: 0 rows
