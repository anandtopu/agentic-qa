/**
 * Agentic QA Orchestrator Workload Identity module — TD-012 (GCP parity for modules/iam).
 *
 * Creates the Google service account the API runs as and binds it to
 * the Kubernetes service account via Workload Identity (the GCP analogue
 * of IRSA). Grants least-privilege access: read the runtime secrets,
 * object-admin on the evidence bucket + use of its CMEK key, and
 * cloudsql.client for the Auth Proxy sidecar.
 *
 * Annotate the KSA with `iam.gke.io/gcp-service-account =`
 * `service_account_email` (see the Helm chart's serviceAccount.annotations).
 */

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

resource "google_service_account" "api" {
  account_id   = "${var.project_name}-${var.environment}-api"
  display_name = "Agentic QA Orchestrator API (${var.environment})"
}

# Read each runtime secret.
resource "google_secret_manager_secret_iam_member" "api" {
  for_each  = var.secret_ids
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

# Read/write evidence objects.
resource "google_storage_bucket_iam_member" "api" {
  bucket = var.evidence_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}

# Use the evidence CMEK key (encrypt/decrypt objects).
resource "google_kms_crypto_key_iam_member" "api" {
  crypto_key_id = var.evidence_kms_key_id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.api.email}"
}

# Connect to Cloud SQL via the Auth Proxy sidecar.
resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Workload Identity: let the KSA impersonate this GSA.
resource "google_service_account_iam_member" "workload_identity" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.namespace}/${var.kubernetes_service_account}]"
}
