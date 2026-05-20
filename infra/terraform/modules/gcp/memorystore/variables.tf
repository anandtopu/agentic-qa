variable "project_name" { type = string }
variable "environment" { type = string }

variable "region" {
  type        = string
  description = "Region for the Memorystore instance."
}

variable "network_id" {
  type        = string
  description = "Authorized VPC self-link (module.vpc.network_id)."
}

variable "tier" {
  type        = string
  description = "BASIC (single node, dev) or STANDARD_HA (prod)."
  default     = "BASIC"
  validation {
    condition     = contains(["BASIC", "STANDARD_HA"], var.tier)
    error_message = "tier must be BASIC or STANDARD_HA."
  }
}

variable "memory_size_gb" {
  type    = number
  default = 1
}

variable "redis_version" {
  type    = string
  default = "REDIS_7_2"
}

variable "labels" {
  type    = map(string)
  default = {}
}
