output "network_id" {
  value       = google_compute_network.this.id
  description = "VPC self-link, consumed by GKE / Cloud SQL / Memorystore."
}

output "network_name" {
  value       = google_compute_network.this.name
  description = "VPC name."
}

output "subnet_id" {
  value       = google_compute_subnetwork.this.id
  description = "Node subnet self-link."
}

output "subnet_name" {
  value       = google_compute_subnetwork.this.name
  description = "Node subnet name."
}

output "pods_range_name" {
  value       = "${local.name}-pods"
  description = "Secondary range name for GKE pods (ip_allocation_policy)."
}

output "services_range_name" {
  value       = "${local.name}-services"
  description = "Secondary range name for GKE services (ip_allocation_policy)."
}

output "private_vpc_connection_id" {
  value       = google_service_networking_connection.this.id
  description = "PSA connection — depend on this before creating Cloud SQL / Memorystore."
}
