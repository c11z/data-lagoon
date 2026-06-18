-- Pass 2: do the 4 null-bearing columns null out together, and who are those rows?
-- Bucket by whether passenger_count is null, then profile by vendor_id + payment_type.
SELECT
    vendor_id,
    payment_type,
    passenger_count IS NULL AS pc_null_group,
    COUNT(*) AS row_count,
    COUNTIF(rate_code IS NULL) AS rate_code_null,
    COUNTIF(store_and_fwd_flag IS NULL) AS store_fwd_null,
    COUNTIF(airport_fee IS NULL) AS airport_fee_null,
    ROUND(AVG(fare_amount), 2) AS avg_fare,
    ROUND(AVG(total_amount), 2) AS avg_total,
    ROUND(AVG(trip_distance), 2) AS avg_distance
FROM `bigquery-public-data.new_york_taxi_trips.tlc_yellow_trips_2022`
GROUP BY pc_null_group, vendor_id, payment_type
ORDER BY row_count DESC;
