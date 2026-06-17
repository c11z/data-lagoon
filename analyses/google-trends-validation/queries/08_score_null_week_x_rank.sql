-- Pass 2b: is the per-rank score-NULL wobble an artifact of week recency?
-- Split each rank's NULL rate into recent (last 3 weeks) vs older weeks.
-- Latest week in this partition is 2026-06-14; recent bucket = week >= 2026-05-31.
SELECT
    `rank`,
    COUNTIF(week >= DATE '2026-05-31') AS recent_rows,
    SAFE_DIVIDE(
        COUNTIF(week >= DATE '2026-05-31' AND score IS NULL),
        COUNTIF(week >= DATE '2026-05-31')
    ) AS recent_null_rate,
    COUNTIF(week < DATE '2026-05-31') AS older_rows,
    SAFE_DIVIDE(
        COUNTIF(week < DATE '2026-05-31' AND score IS NULL),
        COUNTIF(week < DATE '2026-05-31')
    ) AS older_null_rate
FROM `bigquery-public-data.google_trends.top_terms`
WHERE refresh_date = DATE '2026-06-16'
GROUP BY `rank`
ORDER BY `rank`;
