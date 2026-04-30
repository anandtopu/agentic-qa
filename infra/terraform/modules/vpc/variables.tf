variable "project_name" {
  type        = string
  description = "Project tag prefix (typically 'qaforge')."
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)."
}

variable "cluster_name" {
  type        = string
  description = "EKS cluster name — used for subnet auto-discovery tags."
}

variable "cidr" {
  type        = string
  description = "VPC CIDR block."
  default     = "10.42.0.0/16"
}

variable "az_count" {
  type        = number
  description = "Number of AZs to span. Must be 2 or 3."
  default     = 3
  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

variable "single_nat_gateway" {
  type        = bool
  description = "Use one NAT gateway across all AZs (cheaper, dev-only)."
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Extra tags merged into every resource."
  default     = {}
}
