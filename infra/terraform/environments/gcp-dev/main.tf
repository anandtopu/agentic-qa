/**
 * Agentic QA Orchestrator GCP dev environment — TD-012.
 *
 * Smallest viable GCP footprint: BASIC Memorystore, ZONAL Cloud SQL,
 * a 2-node GKE pool. Mirrors environments/dev (AWS). Cloud SQL +
 * Memorystore depend on the vpc module so the Private Service Access
 * peering exists before they request private IPs.
 */

terraform {
  required_version = ">= 1.7.0"

  backend "gcs" {
    # Configure via -backend-config in CI; see ../../README.md.
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  cluster_name = "${var.project_name}-${var.environment}"
}

module "vpc" {
  source        = "../../modules/gcp/vpc"
  project_name  = var.project_name
  environment   = var.environment
  region        = var.region
  subnet_cidr   = var.subnet_cidr
  pods_cidr     = var.pods_cidr
  services_cidr = var.services_cidr
}

module "gke" {
  source              = "../../modules/gcp/gke"
  project_id          = var.project_id
  project_name        = var.project_name
  environment         = var.environment
  cluster_name        = local.cluster_name
  region              = var.region
  network             = module.vpc.network_id
  subnetwork          = module.vpc.subnet_id
  pods_range_name     = module.vpc.pods_range_name
  services_range_name = module.vpc.services_range_name
  machine_type        = "e2-standard-2"
  node_initial_count  = 2
  node_min_count      = 2
  node_max_count      = 4
}

module "cloud_sql" {
  source            = "../../modules/gcp/cloud-sql"
  project_name      = var.project_name
  environment       = var.environment
  region            = var.region
  network_id        = module.vpc.network_id
  tier              = "db-custom-2-4096"
  availability_type = "ZONAL"
  db_username       = var.db_username
  db_password       = var.db_password

  depends_on = [module.vpc]
}

module "memorystore" {
  source         = "../../modules/gcp/memorystore"
  project_name   = var.project_name
  environment    = var.environment
  region         = var.region
  network_id     = module.vpc.network_id
  tier           = "BASIC"
  memory_size_gb = 1

  depends_on = [module.vpc]
}

module "evidence" {
  source       = "../../modules/gcp/gcs-evidence"
  project_name = var.project_name
  environment  = var.environment
  location     = var.evidence_location
}

module "secrets" {
  source       = "../../modules/gcp/secret-manager"
  project_name = var.project_name
  environment  = var.environment
  db_password  = var.db_password
}

module "workload_identity" {
  source                     = "../../modules/gcp/workload-identity"
  project_id                 = var.project_id
  project_name               = var.project_name
  environment                = var.environment
  namespace                  = "aqao"
  kubernetes_service_account = "aqao-api"
  secret_ids                 = module.secrets.secret_ids
  evidence_bucket_name       = module.evidence.bucket_name
  evidence_kms_key_id        = module.evidence.kms_key_id
}
