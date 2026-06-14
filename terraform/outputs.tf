output "project_id" {
  value = var.project_id
}

output "scratch_dataset" {
  value       = "${var.project_id}.${google_bigquery_dataset.scratch.dataset_id}"
  description = "Fully-qualified scratch dataset for any server-side materialization."
}

output "analyst_service_account" {
  value = var.create_service_account ? google_service_account.analyst[0].email : "(none — querying as project owner via ADC)"
}

output "enabled_apis" {
  value = [google_project_service.bigquery.service, google_project_service.bigquerystorage.service]
}

output "manual_quota_note" {
  value = "No native TF resource caps daily bytes-scanned. For a hard daily ceiling: Console -> IAM & Admin -> Quotas -> BigQuery 'Query usage per day (per user)'. Per-query, the harness already sets maximum_bytes_billed."
}
