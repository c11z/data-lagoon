-- Pass 2: does score-NULL correlate with rank? (top_terms, latest partition)
SELECT
    `rank`,
    COUNT(*) AS row_count,
    COUNTIF(score IS NULL) AS null_score,
    SAFE_DIVIDE(COUNTIF(score IS NULL), COUNT(*)) AS null_rate,
    MIN(score) AS min_score,
    MAX(score) AS max_score
FROM `bigquery-public-data.google_trends.top_terms`
WHERE refresh_date = DATE '2026-06-16'
GROUP BY `rank`
ORDER BY `rank`;
