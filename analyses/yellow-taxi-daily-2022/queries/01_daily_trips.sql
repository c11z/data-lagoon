-- Daily yellow-taxi trip counts for 2022 (each row counted as a distinct trip).
-- Scans only pickup_datetime from the explicit 2022 table (cheap). Group by calendar day.
SELECT
    DATE(pickup_datetime) AS trip_date,
    COUNT(*) AS trips
FROM `bigquery-public-data.new_york_taxi_trips.tlc_yellow_trips_2022`
GROUP BY trip_date
ORDER BY trip_date;
