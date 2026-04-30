variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }

variable "client_security_group_ids" {
  type        = list(string)
  description = "SGs allowed to connect on 6379 (typically EKS node SG)."
}

variable "node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "num_cache_clusters" {
  type        = number
  description = "1 = single-node (dev). 2+ = primary + replicas (prod)."
  default     = 1
}

variable "engine_version" {
  type    = string
  default = "7.1"
}

variable "auth_token" {
  type      = string
  sensitive = true
  default   = null
}

variable "snapshot_retention_days" {
  type    = number
  default = 1
}

variable "tags" {
  type    = map(string)
  default = {}
}
