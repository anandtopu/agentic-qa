/**
 * Agentic QA Orchestrator GKE module — TD-012 (GCP parity for modules/eks).
 *
 * VPC-native regional cluster with the default node pool removed and one
 * managed node pool attached, Workload Identity enabled (the GCP analogue
 * of IRSA — the workload-identity module binds a GSA to the API KSA), and
 * auto-repair / auto-upgrade on. Release-channel managed so the control
 * plane tracks a supported version.
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
  common_labels = merge(
    var.labels,
    {
      project     = var.project_name
      environment = var.environment
      managed_by  = "terraform"
    }
  )
}

resource "google_container_cluster" "this" {
  name     = var.cluster_name
  location = var.region

  network    = var.network
  subnetwork = var.subnetwork

  networking_mode = "VPC_NATIVE"

  # Manage the node pool separately so its config can change without
  # recreating the cluster.
  remove_default_node_pool = true
  initial_node_count       = 1

  release_channel {
    channel = var.release_channel
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_ipv4_cidr_block
  }

  resource_labels = local.common_labels

  deletion_protection = var.environment == "prod"
}

resource "google_container_node_pool" "default" {
  name     = "${var.project_name}-${var.environment}-default"
  cluster  = google_container_cluster.this.id
  location = var.region

  autoscaling {
    min_node_count = var.node_min_count
    max_node_count = var.node_max_count
  }

  initial_node_count = var.node_initial_count

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type = var.machine_type
    disk_size_gb = var.node_disk_size_gb
    disk_type    = "pd-standard"

    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    # Required for Workload Identity to work on the nodes.
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = local.common_labels

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}
