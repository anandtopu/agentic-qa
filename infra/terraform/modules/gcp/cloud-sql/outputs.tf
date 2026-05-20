output "instance_name" {
  value = google_sql_database_instance.this.name
}

output "connection_name" {
  value       = google_sql_database_instance.this.connection_name
  description = "PROJECT:REGION:INSTANCE — pass to the Cloud SQL Auth Proxy sidecar (TD-014)."
}

output "private_ip_address" {
  value       = google_sql_database_instance.this.private_ip_address
  description = "Private IP the API connects to (via the proxy on 127.0.0.1)."
}

output "db_name" {
  value = google_sql_database.this.name
}
