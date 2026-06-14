# Optional dedicated analyst service account (most single-user setups don't need this).
resource "google_service_account" "analyst" {
  count        = var.create_service_account ? 1 : 0
  project      = var.project_id
  account_id   = var.service_account_id
  display_name = "data-lagoon BigQuery analyst (query public data, write scratch)"
}

locals {
  sa_member   = var.create_service_account ? ["serviceAccount:${google_service_account.analyst[0].email}"] : []
  all_members = toset(concat(tolist(var.analyst_members), local.sa_member))
}

# Permission to RUN queries (billed to this project). Public datasets are already readable
# by allAuthenticatedUsers; the commonly-forgotten grant is jobUser — without it every query
# fails with "bigquery.jobs.create denied". _member is additive (never clobbers other access).
resource "google_project_iam_member" "job_user" {
  for_each = local.all_members
  project  = var.project_id
  role     = "roles/bigquery.jobUser"
  member   = each.value
}

# Write access scoped to the scratch dataset ONLY (never project-wide dataEditor).
resource "google_bigquery_dataset_iam_member" "scratch_editor" {
  for_each   = local.all_members
  project    = var.project_id
  dataset_id = google_bigquery_dataset.scratch.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = each.value
}
