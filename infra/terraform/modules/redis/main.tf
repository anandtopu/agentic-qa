/**
 * Agentic QA Orchestrator Redis (ElastiCache) module — Story 3.6.1.
 *
 * Single-node in dev, replication group with one replica per AZ in
 * prod. Encryption at-rest + TLS in-transit always.
 */

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.50" }
  }
}

locals {
  common_tags = merge(
    var.tags,
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  )
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.project_name}-${var.environment}-redis-"
  vpc_id      = var.vpc_id
  description = "Allow Redis from EKS workers only."

  ingress {
    description     = "Redis from EKS workers"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = var.client_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
  lifecycle { create_before_destroy = true }
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.project_name}-${var.environment}-redis"
  subnet_ids = var.subnet_ids
  tags       = local.common_tags
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id        = "${var.project_name}-${var.environment}"
  description                 = "Agentic QA Orchestrator Redis (${var.environment})"
  engine                      = "redis"
  engine_version              = var.engine_version
  node_type                   = var.node_type
  parameter_group_name        = "default.redis7"
  port                        = 6379
  subnet_group_name           = aws_elasticache_subnet_group.this.name
  security_group_ids          = [aws_security_group.redis.id]
  num_cache_clusters          = var.num_cache_clusters
  automatic_failover_enabled  = var.num_cache_clusters > 1
  multi_az_enabled            = var.num_cache_clusters > 1
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true
  auth_token                  = var.auth_token
  apply_immediately           = false
  snapshot_retention_limit    = var.snapshot_retention_days

  tags = local.common_tags
}
