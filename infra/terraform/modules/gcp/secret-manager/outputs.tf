output "secret_ids" {
  value       = { for k, v in google_secret_manager_secret.this : k => v.id }
  description = "Map of secret name -> fully-qualified secret id. Consumed by the workload-identity module."
}

output "secret_names" {
  value       = { for k, v in google_secret_manager_secret.this : k => v.secret_id }
  description = "Map of secret name -> short secret_id, for the Helm chart's env references."
}
