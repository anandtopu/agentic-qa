/**
 * Agentic QA Orchestrator IAM (IRSA) module — Story 3.6.1.
 *
 * Creates the IAM role the API service account assumes via OIDC,
 * with read access to the runtime secrets and read/write to the
 * evidence-store bucket. Bind via the Helm chart's
 * ``serviceAccount.annotations`` (eks.amazonaws.com/role-arn).
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

  oidc_provider = replace(var.oidc_provider_url, "https://", "")
}

data "aws_iam_policy_document" "api_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${var.service_account_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${var.project_name}-${var.environment}-api"
  assume_role_policy = data.aws_iam_policy_document.api_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "api_inline" {
  statement {
    sid     = "ReadSecrets"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [for arn in values(var.secret_arns) : arn]
  }

  statement {
    sid       = "DecryptSecretsKms"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "ForAnyValue:StringEquals"
      variable = "kms:ResourceAliases"
      values   = ["alias/aws/secretsmanager"]
    }
  }

  statement {
    sid     = "EvidenceObjectsRW"
    effect  = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      var.evidence_bucket_arn,
      "${var.evidence_bucket_arn}/*",
    ]
  }

  statement {
    sid       = "EvidenceKmsUse"
    effect    = "Allow"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.evidence_kms_key_arn]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "${var.project_name}-${var.environment}-api"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_inline.json
}
