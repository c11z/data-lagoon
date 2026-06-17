-- Free metadata: latest partition + row count per google_trends table.
-- INFORMATION_SCHEMA.PARTITIONS scans 0 bytes; used to pin a literal refresh_date
-- so the Pass-1 checks get real partition pruning (no dynamic-subquery full scan).
SELECT
    table_name,
    MAX(partition_id) AS latest_partition,
    SUM(total_rows) AS rows_all_partitions
FROM `bigquery-public-data.google_trends.INFORMATION_SCHEMA.PARTITIONS`
WHERE
    table_name IN (
        'top_terms',
        'top_rising_terms',
        'international_top_terms',
        'international_top_rising_terms'
    )
GROUP BY table_name
ORDER BY table_name;
