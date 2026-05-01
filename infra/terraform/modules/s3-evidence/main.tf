/**
 * Agentic QA Orchestrator evidence-store S3 bucket — Story 3.6.1.
 *
 * Versioned + SSE-KMS + bucket-owner-enforced ACLs + lifecycle:
 *
 *   - retain current version forever (legal evidence requirement);
 *   - transition non-current versions to STANDARD_IA after 30 days;
 *   - expire non-current versions after 365 days.
 *
 * The bucket is private — IRSA grants the API service account
 * read/write via the iam module.
 */

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.50" }
  }
}

locals {
  bucket_name = coalesce(var.bucket_name, "${var.project_name}-${var.environment}-evidence")

  common_tags = merge(
    var.tags,
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Purpose     = "aqao-evidence-store"
    }
  )
}

resource "aws_kms_key" "evidence" {
  description             = "Agentic QA Orchestrator evidence-store encryption key (${var.environment})"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = local.common_tags
}

resource "aws_kms_alias" "evidence" {
  name          = "alias/${var.project_name}-${var.environment}-evidence"
  target_key_id = aws_kms_key.evidence.id
}

resource "aws_s3_bucket" "evidence" {
  bucket = local.bucket_name
  tags   = local.common_tags
}

resource "aws_s3_bucket_ownership_controls" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket                  = aws_s3_bucket.evidence.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.evidence.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    id     = "noncurrent-transition-and-expiration"
    status = "Enabled"
    filter {}

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
