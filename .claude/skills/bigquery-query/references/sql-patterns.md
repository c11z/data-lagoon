# Common google_trends SQL patterns

Prefer compiling from the semantic layer (`spec_lookup.py --compile`). Use these only as the
raw-SQL fallback. Every pattern is partition-filtered on `refresh_date` (cost safety).

## 1. Top terms for the latest published week (with latest-refresh dedup)

The most common correct shape — avoids double-counting across refreshes.

```sql
WITH latest AS (
    SELECT MAX(refresh_date) AS rd
    FROM `bigquery-public-data.google_trends.top_terms`
    WHERE refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)
)
SELECT dma_name, term, rank, score
FROM `bigquery-public-data.google_trends.top_terms`
WHERE refresh_date = (SELECT rd FROM latest)
    AND rank <= 10
ORDER BY dma_name, rank
```

## 2. Fastest-rising terms (percent_gain) for a recent window

```sql
SELECT term, AVG(percent_gain) AS avg_gain
FROM `bigquery-public-data.google_trends.top_rising_terms`
WHERE refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY term
ORDER BY avg_gain DESC
LIMIT 20
```

## 3. Average relative interest by term (national, US DMAs)

```sql
SELECT term, AVG(score) AS avg_score
FROM `bigquery-public-data.google_trends.top_terms`
WHERE refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    AND score IS NOT NULL
GROUP BY term
ORDER BY avg_score DESC
LIMIT 25
```

## 4. International, one country

```sql
SELECT term, rank, score
FROM `bigquery-public-data.google_trends.international_top_terms`
WHERE refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    AND country_code = 'GB'
    AND rank <= 10
ORDER BY refresh_date DESC, rank
```

## Rules of thumb

- **Always** put a `refresh_date` predicate in the WHERE (or in a CTE that the main query
  filters on). No exceptions — it's the partition column.
- Use `rank <= N` (segments `top_5` / `top_10`) instead of `ORDER BY ... LIMIT N` when you
  want the *ranked* set — `LIMIT` doesn't reduce scan cost.
- Lint every saved query: `uv run sqlfluff lint <file>.sql` (BigQuery dialect, keywords
  UPPER, identifiers lower).
