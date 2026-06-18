-- Grain test for yellow taxi (2022): is there a column set that uniquely identifies a row?
-- Compare COUNT(*) to COUNT(DISTINCT key) for progressively wider candidate keys.
--   K1 = vendor + pickup/dropoff time + pickup/dropoff zone (spatiotemporal)
--   K2 = K1 + passenger/distance/fare/total (transaction detail)
-- If a distinct count == total_rows, that key is unique; if it stays below, duplicates exist.
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT TO_JSON_STRING(STRUCT(
        vendor_id,
        pickup_datetime,
        dropoff_datetime,
        pickup_location_id,
        dropoff_location_id
    ))) AS distinct_k1_spatiotemporal,
    COUNT(DISTINCT TO_JSON_STRING(STRUCT(
        vendor_id,
        pickup_datetime,
        dropoff_datetime,
        pickup_location_id,
        dropoff_location_id,
        passenger_count,
        trip_distance,
        fare_amount,
        total_amount
    ))) AS distinct_k2_plus_txn
FROM `bigquery-public-data.new_york_taxi_trips.tlc_yellow_trips_2022`;
