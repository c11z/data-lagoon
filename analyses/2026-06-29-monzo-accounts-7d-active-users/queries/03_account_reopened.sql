-- Raw extract: one row per account-reopen event (account_reopened).
SELECT
    reopened_ts,
    account_id_hashed
FROM `analytics-take-home-test.monzo_datawarehouse.account_reopened`;
