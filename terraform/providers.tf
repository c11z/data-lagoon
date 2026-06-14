terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Local state for this single-user sandbox (terraform.tfstate is gitignored).
  # To graduate to remote state, create a versioned bucket and uncomment:
  # backend "gcs" {
  #   bucket = "REPLACE-with-your-state-bucket"
  #   prefix = "data-lagoon/terraform"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
  # Auth via Application Default Credentials: `gcloud auth application-default login`.
  # Intentionally NO `credentials = file("key.json")` — we never use service-account keys.
}
