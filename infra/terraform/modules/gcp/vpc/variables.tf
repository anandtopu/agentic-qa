variable "project_name" {
  type        = string
  description = "Project label/name prefix (typically 'aqao')."
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)."
}

variable "region" {
  type        = string
  description = "GCP region for the subnet, router, and NAT."
}

variable "subnet_cidr" {
  type        = string
  description = "Primary CIDR for the node subnet."
  default     = "10.42.0.0/20"
}

variable "pods_cidr" {
  type        = string
  description = "Secondary range for GKE pods (VPC-native)."
  default     = "10.43.0.0/16"
}

variable "services_cidr" {
  type        = string
  description = "Secondary range for GKE services (VPC-native)."
  default     = "10.44.0.0/20"
}

variable "private_service_prefix_length" {
  type        = number
  description = "Prefix length of the Private Service Access range (for Cloud SQL + Memorystore)."
  default     = 20
}
