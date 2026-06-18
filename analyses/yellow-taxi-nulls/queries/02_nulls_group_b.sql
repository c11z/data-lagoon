-- Yellow taxi NULL profile, columns 11-20, single year (2022). See group A header.
SELECT
    COUNT(*) AS total_rows,
    COUNTIF(mta_tax IS NULL) AS null_mta_tax,
    COUNTIF(tip_amount IS NULL) AS null_tip_amount,
    COUNTIF(tolls_amount IS NULL) AS null_tolls_amount,
    COUNTIF(imp_surcharge IS NULL) AS null_imp_surcharge,
    COUNTIF(airport_fee IS NULL) AS null_airport_fee,
    COUNTIF(total_amount IS NULL) AS null_total_amount,
    COUNTIF(pickup_location_id IS NULL) AS null_pickup_location_id,
    COUNTIF(dropoff_location_id IS NULL) AS null_dropoff_location_id,
    COUNTIF(data_file_year IS NULL) AS null_data_file_year,
    COUNTIF(data_file_month IS NULL) AS null_data_file_month
FROM `bigquery-public-data.new_york_taxi_trips.tlc_yellow_trips_2022`;
