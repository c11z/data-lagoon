-- Raw extract: one row per account-closure EVENT (account_closed).
-- Event grain (an account may appear more than once); explicit columns, no SELECT *.
SELECT
    closed_ts,
    account_id_hashed
FROM `analytics-take-home-test.monzo_datawarehouse.account_closed`;
