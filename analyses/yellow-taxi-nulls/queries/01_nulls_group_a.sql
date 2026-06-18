-- Yellow taxi NULL profile, columns 1-10, single year (2022) for cost control.
-- Split into two column-groups so each stays under the 5 GiB hard cap (a full
-- all-column scan of yellow 2022 is ~7 GiB). Filter _TABLE_SUFFIX = year.
SELECT
    COUNT(*) AS total_rows,
    COUNTIF(vendor_id IS NULL) AS null_vendor_id,
    COUNTIF(pickup_datetime IS NULL) AS null_pickup_datetime,
    COUNTIF(dropoff_datetime IS NULL) AS null_dropoff_datetime,
    COUNTIF(passenger_count IS NULL) AS null_passenger_count,
    COUNTIF(trip_distance IS NULL) AS null_trip_distance,
    COUNTIF(rate_code IS NULL) AS null_rate_code,
    COUNTIF(store_and_fwd_flag IS NULL) AS null_store_and_fwd_flag,
    COUNTIF(payment_type IS NULL) AS null_payment_type,
    COUNTIF(fare_amount IS NULL) AS null_fare_amount,
    COUNTIF(extra IS NULL) AS null_extra
FROM `bigquery-public-data.new_york_taxi_trips.tlc_yellow_trips_2022`;
