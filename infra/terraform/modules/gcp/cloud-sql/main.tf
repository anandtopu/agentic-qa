/**
 * Agentic QA Orchestrator Cloud SQL module — TD-012 (GCP parity for modules/rds).
 *
 * Postgres 16 with private IP (no public endpoint), automated backups +
 * point-in-time recovery (Story 3.6.3 RPO target), and REGIONAL HA in
 * prod. Reaches the VPC over Private Service Access, so the composing
 * environment must `depends_on` the vpc module's PSA connection.
 *
 * The `connection_name` output feeds the Cloud SQL Auth Proxy sidecar
 * declared via the Helm chart's `extraContainers` (see TD-014).
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

resource "google_sql_database_instance" "this" {
  name                = local.name
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = var.environment == "prod"

  settings {
    tier              = var.tier
    availability_type = var.availability_type
    disk_size         = var.disk_size_gb
    disk_type         = "PD_SSD"
    disk_autoresize   = true
    user_labels       = local.common_labels

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = var.transaction_log_retention_days
      start_time                     = "02:00"
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
      ssl_mode        = "ENCRYPTED_ONLY"
    }
  }
}

resource "google_sql_database" "this" {
  name     = var.db_name
  instance = google_sql_database_instance.this.name
}

resource "google_sql_user" "this" {
  name     = var.db_username
  instance = google_sql_database_instance.this.name
  password = var.db_password
}
