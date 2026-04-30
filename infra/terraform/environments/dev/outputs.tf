output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "redis_primary_endpoint" {
  value = module.redis.primary_endpoint
}

output "evidence_bucket_name" {
  value = module.evidence.bucket_name
}

output "api_iam_role_arn" {
  value       = module.iam.api_role_arn
  description = "Use this ARN in the Helm chart's serviceAccount.annotations."
}
