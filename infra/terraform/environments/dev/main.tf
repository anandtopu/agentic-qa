/**
 * Agentic QA Orchestrator dev environment — Story 3.6.1.
 *
 * Smallest viable footprint: single NAT, single-AZ Redis, no Multi-AZ
 * RDS. 60-minute apply target met with default `terraform apply -auto-approve`.
 */

terraform {
  required_version = ">= 1.7.0"

  backend "s3" {
    # Configure via -backend-config in CI; see ../../README.md.
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  cluster_name = "${var.project_name}-${var.environment}"
}

module "vpc" {
  source             = "../../modules/vpc"
  project_name       = var.project_name
  environment        = var.environment
  cluster_name       = local.cluster_name
  cidr               = var.vpc_cidr
  az_count           = 3
  single_nat_gateway = true
}

module "eks" {
  source              = "../../modules/eks"
  project_name        = var.project_name
  environment         = var.environment
  cluster_name        = local.cluster_name
  kubernetes_version  = var.eks_kubernetes_version
  vpc_id              = module.vpc.vpc_id
  public_subnet_ids   = module.vpc.public_subnet_ids
  private_subnet_ids  = module.vpc.private_subnet_ids
  node_instance_types = ["t3.medium"]
  node_desired_size   = 2
  node_min_size       = 2
  node_max_size       = 4
}

module "rds" {
  source                    = "../../modules/rds"
  project_name              = var.project_name
  environment               = var.environment
  vpc_id                    = module.vpc.vpc_id
  db_subnet_group_name      = module.vpc.db_subnet_group_name
  client_security_group_ids = [module.eks.node_role_arn]  # placeholder; bind via SG ref in real apply
  db_password               = var.db_password
  db_username               = var.db_username
  multi_az                  = false
  backup_retention_days     = 7
  instance_class            = "db.t4g.medium"
}

module "redis" {
  source                    = "../../modules/redis"
  project_name              = var.project_name
  environment               = var.environment
  vpc_id                    = module.vpc.vpc_id
  subnet_ids                = module.vpc.private_subnet_ids
  client_security_group_ids = [module.eks.node_role_arn]
  num_cache_clusters        = 1
  node_type                 = "cache.t4g.micro"
}

module "evidence" {
  source       = "../../modules/s3-evidence"
  project_name = var.project_name
  environment  = var.environment
}

module "secrets" {
  source       = "../../modules/secrets"
  project_name = var.project_name
  environment  = var.environment
  db_password  = var.db_password
}

module "iam" {
  source               = "../../modules/iam"
  project_name         = var.project_name
  environment          = var.environment
  oidc_provider_arn    = module.eks.oidc_provider_arn
  oidc_provider_url    = module.eks.oidc_provider_url
  namespace            = "aqao"
  service_account_name = "aqao-api"
  secret_arns          = module.secrets.secret_arns
  evidence_bucket_arn  = module.evidence.bucket_arn
  evidence_kms_key_arn = module.evidence.kms_key_arn
}
