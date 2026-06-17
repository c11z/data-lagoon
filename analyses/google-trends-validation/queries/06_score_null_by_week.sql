-- Pass 2: does score-NULL correlate with week? (top_terms, latest partition)
-- Each refresh_date re-reports several weeks; test whether scoring is week-dependent.
SELECT
    week,
    COUNT(*) AS row_count,
    COUNTIF(score IS NULL) AS null_score,
    SAFE_DIVIDE(COUNTIF(score IS NULL), COUNT(*)) AS null_rate
FROM `bigquery-public-data.google_trends.top_terms`
WHERE refresh_date = DATE '2026-06-16'
GROUP BY week
ORDER BY week;
