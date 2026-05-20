output "host" {
  value       = google_redis_instance.this.host
  description = "Private IP of the Redis primary."
}

output "port" {
  value = google_redis_instance.this.port
}

output "auth_string" {
  value       = google_redis_instance.this.auth_string
  description = "AUTH token (auth_enabled = true)."
  sensitive   = true
}

output "current_location_id" {
  value = google_redis_instance.this.current_location_id
}
