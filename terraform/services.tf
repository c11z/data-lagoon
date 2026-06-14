# Enable the APIs the harness needs. disable_on_destroy = false so a `terraform destroy`
# doesn't yank BigQuery from the whole project.
resource "google_project_service" "bigquery" {
  project            = var.project_id
  service            = "bigquery.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "bigquerystorage" {
  project            = var.project_id
  service            = "bigquerystorage.googleapis.com"
  disable_on_destroy = false
}
