/**
 * Agentic QA Orchestrator evidence-store GCS module — TD-012 (GCP parity for modules/s3-evidence).
 *
 * Versioned bucket with CMEK (customer-managed KMS key), uniform
 * bucket-level access, public-access-prevention enforced, and a
 * lifecycle policy that mirrors the S3 module:
 *   - keep the live object forever (legal evidence requirement);
 *   - move non-current versions to NEARLINE after 30 days;
 *   - delete non-current versions after 365 days.
 *
 * The workload-identity module grants the API service account
 * object-admin on the bucket and use of the KMS key.
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

locals {
  name        = "${var.project_name}-${var.environment}"
  bucket_name = coalesce(var.bucket_name, "${var.project_name}-${var.environment}-evidence")

  common_labels = merge(
    var.labels,
    {
      project     = var.project_name
      environment = var.environment
      managed_by  = "terraform"
      purpose     = "aqao-evidence-store"
    }
  )
}

resource "google_kms_key_ring" "this" {
  name     = "${local.name}-evidence"
  location = var.location
}

resource "google_kms_crypto_key" "evidence" {
  name            = "${local.name}-evidence"
  key_ring        = google_kms_key_ring.this.id
  rotation_period = var.kms_rotation_period
  labels          = local.common_labels

  lifecycle {
    prevent_destroy = false
  }
}

# The GCS service agent must be allowed to use the CMEK key, or bucket
# creation with default_kms_key_name fails.
data "google_storage_project_service_account" "gcs" {}

resource "google_kms_crypto_key_iam_member" "gcs" {
  crypto_key_id = google_kms_crypto_key.evidence.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}

resource "google_storage_bucket" "evidence" {
  name                        = local.bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.environment != "prod"
  labels                      = local.common_labels

  versioning {
    enabled = true
  }

  encryption {
    default_kms_key_name = google_kms_crypto_key.evidence.id
  }

  lifecycle_rule {
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
    condition {
      days_since_noncurrent_time = 30
    }
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      days_since_noncurrent_time = 365
    }
  }

  depends_on = [google_kms_crypto_key_iam_member.gcs]
}
