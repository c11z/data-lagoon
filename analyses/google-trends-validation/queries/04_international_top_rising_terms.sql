-- Pass 1: international_top_rising_terms grain + NULL ratios on the latest partition.
-- Declared grain within a refresh_date: (country_code, region_code, term, week).
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT TO_JSON_STRING(
        STRUCT(country_code, region_code, term, week)
    )) AS distinct_grain,
    COUNTIF(week IS NULL) AS null_week,
    COUNTIF(score IS NULL) AS null_score,
    COUNTIF(rank IS NULL) AS null_rank,
    COUNTIF(percent_gain IS NULL) AS null_percent_gain,
    COUNTIF(country_code IS NULL) AS null_country_code,
    COUNTIF(country_name IS NULL) AS null_country_name,
    COUNTIF(region_code IS NULL) AS null_region_code,
    COUNTIF(region_name IS NULL) AS null_region_name,
    COUNTIF(term IS NULL) AS null_term
FROM `bigquery-public-data.google_trends.international_top_rising_terms`
WHERE refresh_date = DATE '2026-06-16';
