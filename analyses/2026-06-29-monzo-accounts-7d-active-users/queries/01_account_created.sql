-- Raw extract: one row per account-creation event (account_created).
-- Row-level pull (the model needs per-account rows); explicit columns, no SELECT *.
SELECT
    created_ts,
    account_type,
    account_id_hashed,
    user_id_hashed
FROM `analytics-take-home-test.monzo_datawarehouse.account_created`;
