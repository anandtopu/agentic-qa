/**
 * Agentic QA Orchestrator Secret Manager module — TD-012 (GCP parity for modules/secrets).
 *
 * Holds the runtime secrets the API container reads at boot
 * (audit_hmac_key, github_webhook_secret, anthropic_api_key, db_password).
 * A null input value means "generate a random secret". The
 * workload-identity module grants the API service account
 * secretAccessor on each of these.
 */

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }
  }
}

locals {
  common_labels = merge(
    var.labels,
    {
      project     = var.project_name
      environment = var.environment
      managed_by  = "terraform"
    }
  )

  # Secret name -> initial value (null = generate random).
  secrets = {
    audit_hmac_key        = var.audit_hmac_key
    github_webhook_secret = var.github_webhook_secret
    anthropic_api_key     = var.anthropic_api_key
    db_password           = var.db_password
  }
}

# Generate a random value for every secret name; only used where the
# operator didn't supply one (see the version ternary below). Keying
# for_each off the static names avoids using sensitive values as keys.
resource "random_password" "generated" {
  for_each = toset(keys(local.secrets))
  length   = 64
  special  = false
}

resource "google_secret_manager_secret" "this" {
  for_each  = toset(keys(local.secrets))
  secret_id = "${var.project_name}-${var.environment}-${each.key}"
  labels    = local.common_labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "this" {
  for_each    = google_secret_manager_secret.this
  secret      = each.value.id
  secret_data = local.secrets[each.key] != null ? local.secrets[each.key] : random_password.generated[each.key].result
}
