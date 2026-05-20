output "cluster_name" {
  value = module.gke.cluster_name
}

output "cluster_endpoint" {
  value = module.gke.cluster_endpoint
}

output "cloud_sql_connection_name" {
  value       = module.cloud_sql.connection_name
  description = "Pass to the Cloud SQL Auth Proxy sidecar (Helm extraContainers, TD-014)."
}

output "redis_host" {
  value = module.memorystore.host
}

output "evidence_bucket_name" {
  value = module.evidence.bucket_name
}

output "api_service_account_email" {
  value       = module.workload_identity.service_account_email
  description = "Annotate the KSA with iam.gke.io/gcp-service-account = this."
}
