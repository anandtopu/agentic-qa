output "cluster_name" {
  value = google_container_cluster.this.name
}

output "cluster_endpoint" {
  value       = google_container_cluster.this.endpoint
  description = "GKE API server endpoint."
}

output "cluster_ca_certificate" {
  value       = google_container_cluster.this.master_auth[0].cluster_ca_certificate
  description = "Base64 cluster CA cert for kubeconfig."
  sensitive   = true
}

output "workload_pool" {
  value       = "${var.project_id}.svc.id.goog"
  description = "Workload Identity pool — used to bind a GSA to a KSA."
}

output "location" {
  value = google_container_cluster.this.location
}
