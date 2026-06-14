# Ephemeral scratch dataset. The two-phase notebooks persist results as on-disk parquet,
# so this is only for the occasional server-side materialization. Tables auto-expire.
resource "google_bigquery_dataset" "scratch" {
  project                     = var.project_id
  dataset_id                  = var.scratch_dataset_id
  location                    = var.bq_location
  description                 = "data-lagoon scratch — ephemeral; tables auto-expire."
  default_table_expiration_ms = var.scratch_table_expiration_days * 24 * 60 * 60 * 1000
  delete_contents_on_destroy  = true

  depends_on = [google_project_service.bigquery]
}
