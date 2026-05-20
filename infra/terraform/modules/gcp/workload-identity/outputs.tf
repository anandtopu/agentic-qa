output "service_account_email" {
  value       = google_service_account.api.email
  description = "Bind to the KSA via the iam.gke.io/gcp-service-account annotation."
}

output "service_account_id" {
  value = google_service_account.api.id
}
