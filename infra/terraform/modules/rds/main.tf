/**
 * QAForge RDS Postgres module — Story 3.6.1.
 *
 * Postgres 16 with PITR (Story 3.6.3 RPO target = 5 min). Multi-AZ
 * in prod for fast failover; single-AZ in dev to keep cost down.
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

resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-${var.environment}-rds-"
  vpc_id      = var.vpc_id
  description = "Allow Postgres from EKS workers only."

  ingress {
    description     = "Postgres from EKS workers"
    from_port       = 5432
    to_port         = 5432
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

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.project_name}-${var.environment}-pg16-"
  family      = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }

  tags = local.common_tags
  lifecycle { create_before_destroy = true }
}

resource "aws_db_instance" "this" {
  identifier              = "${var.project_name}-${var.environment}"
  engine                  = "postgres"
  engine_version          = "16.4"
  instance_class          = var.instance_class
  allocated_storage       = var.allocated_storage_gb
  max_allocated_storage   = var.max_allocated_storage_gb
  storage_type            = "gp3"
  storage_encrypted       = true
  db_name                 = var.db_name
  username                = var.db_username
  password                = var.db_password
  port                    = 5432
  multi_az                = var.multi_az
  publicly_accessible     = false
  db_subnet_group_name    = var.db_subnet_group_name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  parameter_group_name    = aws_db_parameter_group.this.name
  backup_retention_period = var.backup_retention_days
  backup_window           = "02:00-03:00"
  maintenance_window      = "Sun:03:30-Sun:04:30"
  deletion_protection     = var.environment == "prod"
  skip_final_snapshot     = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project_name}-${var.environment}-final-${formatdate("YYYYMMDDhhmmss", timestamp())}" : null
  copy_tags_to_snapshot   = true
  performance_insights_enabled = true
  performance_insights_retention_period = 7
  monitoring_interval     = 60
  monitoring_role_arn     = aws_iam_role.monitoring.arn
  apply_immediately       = false

  tags = local.common_tags

  lifecycle {
    ignore_changes = [final_snapshot_identifier, password]
  }
}

resource "aws_iam_role" "monitoring" {
  name = "${var.project_name}-${var.environment}-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "monitoring" {
  role       = aws_iam_role.monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
