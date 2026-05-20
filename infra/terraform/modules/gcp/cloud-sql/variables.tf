variable "project_name" { type = string }
variable "environment" { type = string }

variable "region" {
  type        = string
  description = "Region for the Cloud SQL instance."
}

variable "network_id" {
  type        = string
  description = "VPC self-link for the private IP (module.vpc.network_id)."
}

variable "tier" {
  type        = string
  description = "Cloud SQL machine tier (e.g. db-custom-2-4096)."
  default     = "db-custom-2-4096"
}

variable "availability_type" {
  type        = string
  description = "ZONAL (dev) or REGIONAL (prod HA)."
  default     = "ZONAL"
  validation {
    condition     = contains(["ZONAL", "REGIONAL"], var.availability_type)
    error_message = "availability_type must be ZONAL or REGIONAL."
  }
}

variable "disk_size_gb" {
  type    = number
  default = 50
}

variable "transaction_log_retention_days" {
  type        = number
  description = "PITR transaction-log retention window (1-7)."
  default     = 7
}

variable "db_name" {
  type    = string
  default = "aqao"
}

variable "db_username" {
  type    = string
  default = "aqao"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "labels" {
  type    = map(string)
  default = {}
}
