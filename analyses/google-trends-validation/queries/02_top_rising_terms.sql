-- Pass 1: top_rising_terms grain + NULL ratios on the latest partition.
-- Declared grain within a refresh_date: (dma_id, term, week). Adds percent_gain.
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT TO_JSON_STRING(STRUCT(dma_id, term, week))) AS distinct_grain,
    COUNTIF(week IS NULL) AS null_week,
    COUNTIF(score IS NULL) AS null_score,
    COUNTIF(rank IS NULL) AS null_rank,
    COUNTIF(percent_gain IS NULL) AS null_percent_gain,
    COUNTIF(dma_name IS NULL) AS null_dma_name,
    COUNTIF(dma_id IS NULL) AS null_dma_id,
    COUNTIF(term IS NULL) AS null_term
FROM `bigquery-public-data.google_trends.top_rising_terms`
WHERE refresh_date = DATE '2026-06-16';
