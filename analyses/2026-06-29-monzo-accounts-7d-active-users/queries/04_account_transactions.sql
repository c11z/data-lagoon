-- Raw extract: one row per (account, day) with >=1 transaction (account_transactions).
-- Sparse panel; source column `date` aliased to txn_date for cross-engine ergonomics.
SELECT
    `date` AS txn_date,
    account_id_hashed,
    transactions_num
FROM `analytics-take-home-test.monzo_datawarehouse.account_transactions`;
