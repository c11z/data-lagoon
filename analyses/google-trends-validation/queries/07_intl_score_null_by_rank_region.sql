-- Pass 2: international score-NULL vs rank, and check region_code empty-string usage.
SELECT
    `rank`,
    COUNT(*) AS row_count,
    COUNTIF(score IS NULL) AS null_score,
    SAFE_DIVIDE(COUNTIF(score IS NULL), COUNT(*)) AS null_rate,
    COUNTIF(region_code = '') AS empty_region_code,
    COUNTIF(region_code IS NULL) AS null_region_code
FROM `bigquery-public-data.google_trends.international_top_terms`
WHERE refresh_date = DATE '2026-06-16'
GROUP BY `rank`
ORDER BY `rank`;
