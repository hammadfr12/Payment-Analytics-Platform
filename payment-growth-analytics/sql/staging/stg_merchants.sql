-- staging/stg_merchants.sql
-- Clean projection of merchant dimension.

CREATE OR REPLACE TABLE stg_merchants AS
SELECT
    CAST(merchant_id AS VARCHAR)       AS merchant_id,
    CAST(merchant_name AS VARCHAR)     AS merchant_name,
    CAST(industry AS VARCHAR)          AS industry,
    CAST(mcc AS VARCHAR)               AS mcc,
    CAST(merchant_segment AS VARCHAR)  AS merchant_segment,
    CAST(account_manager AS VARCHAR)   AS account_manager,
    CAST(country AS VARCHAR)           AS country,
    CAST(onboarded_at AS TIMESTAMP)    AS onboarded_at
FROM raw_merchants;
