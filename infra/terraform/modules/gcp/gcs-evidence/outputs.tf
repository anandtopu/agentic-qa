output "bucket_name" {
  value = google_storage_bucket.evidence.name
}

output "bucket_url" {
  value = google_storage_bucket.evidence.url
}

output "kms_key_id" {
  value       = google_kms_crypto_key.evidence.id
  description = "CMEK key id — granted to the API service account by the workload-identity module."
}
