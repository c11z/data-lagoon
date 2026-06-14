# Billing budget ALERT — gated behind create_budget because it needs billing-account-level
# IAM (roles/billing.admin or budget editor), which is a different scope than project IAM.
# NOTE: a budget only alerts; it never stops spend. The hard guardrail is maximum_bytes_billed.
data "google_project" "this" {
  count      = var.create_budget ? 1 : 0
  project_id = var.project_id
}

resource "google_billing_budget" "monthly" {
  count           = var.create_budget ? 1 : 0
  billing_account = var.billing_account
  display_name    = "data-lagoon monthly budget"

  budget_filter {
    # budget_filter.projects requires the project NUMBER, not the id.
    projects = ["projects/${data.google_project.this[0].number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount_usd)
    }
  }

  dynamic "threshold_rules" {
    for_each = [0.5, 0.9, 1.0]
    content {
      threshold_percent = threshold_rules.value
    }
  }
}
