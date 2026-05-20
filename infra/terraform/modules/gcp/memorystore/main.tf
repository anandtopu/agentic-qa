/**
 * Agentic QA Orchestrator Memorystore module — TD-012 (GCP parity for modules/redis).
 *
 * Memorystore for Redis: BASIC (single node) in dev, STANDARD_HA in
 * prod. Reaches the VPC over Private Service Access, AUTH on, and TLS
 * in-transit (SERVER_AUTHENTICATION) — mirroring the encryption posture
 * of the AWS ElastiCache module.
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
  name = "${var.project_name}-${var.environment}"

  common_labels = merge(
    var.labels,
    {
      project     = var.project_name
      environment = var.environment
      managed_by  = "terraform"
    }
  )
}

resource "google_redis_instance" "this" {
  name           = local.name
  display_name   = "Agentic QA Orchestrator Redis (${var.environment})"
  tier           = var.tier
  memory_size_gb = var.memory_size_gb
  region         = var.region

  authorized_network = var.network_id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  redis_version           = var.redis_version
  auth_enabled            = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  labels = local.common_labels
}
