variable "project_id" {
  type        = string
  default     = "c11z-data-lagoon"
  description = "The billing/query project (public-data queries bill bytes scanned here)."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Default provider region (not the BigQuery dataset location)."
}

variable "bq_location" {
  type        = string
  default     = "US"
  description = "Dataset/job location. MUST match the public data (google_trends is US multi-region)."
}

variable "scratch_dataset_id" {
  type        = string
  default     = "scratch"
  description = "Ephemeral dataset for any materialized results (the harness mostly uses on-disk parquet)."
}

variable "scratch_table_expiration_days" {
  type        = number
  default     = 1
  description = "Auto-expire scratch tables to avoid storage cost (BigQuery minimum is 1 hour)."
}

variable "analyst_members" {
  type        = set(string)
  default     = []
  description = "IAM members to grant query access, e.g. [\"user:you@example.com\"]. Empty = query as project owner."
}

variable "create_service_account" {
  type        = bool
  default     = false
  description = "Create a dedicated analyst service account (in addition to analyst_members)."
}

variable "service_account_id" {
  type        = string
  default     = "bq-sandbox-analyst"
  description = "Account id for the optional analyst service account."
}

variable "create_budget" {
  type        = bool
  default     = false
  description = "Create a billing budget ALERT. Requires billing-account-level IAM (separate from project IAM)."
}

variable "billing_account" {
  type        = string
  default     = ""
  description = "Billing account id (required only when create_budget = true)."
}

variable "budget_amount_usd" {
  type        = number
  default     = 50
  description = "Monthly budget amount in USD for the alert thresholds (alerts only — not a hard cap)."
}
