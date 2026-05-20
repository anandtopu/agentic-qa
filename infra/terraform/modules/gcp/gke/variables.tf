variable "project_id" {
  type        = string
  description = "GCP project ID (used to derive the Workload Identity pool)."
}

variable "project_name" { type = string }
variable "environment" { type = string }

variable "cluster_name" {
  type        = string
  description = "GKE cluster name."
}

variable "region" {
  type        = string
  description = "Region for the regional cluster + node pool."
}

variable "network" {
  type        = string
  description = "VPC self-link (module.vpc.network_id)."
}

variable "subnetwork" {
  type        = string
  description = "Node subnet self-link (module.vpc.subnet_id)."
}

variable "pods_range_name" {
  type        = string
  description = "Secondary range name for pods (module.vpc.pods_range_name)."
}

variable "services_range_name" {
  type        = string
  description = "Secondary range name for services (module.vpc.services_range_name)."
}

variable "release_channel" {
  type        = string
  description = "GKE release channel: RAPID, REGULAR, or STABLE."
  default     = "REGULAR"
}

variable "master_ipv4_cidr_block" {
  type        = string
  description = "RFC-1918 /28 for the private control-plane endpoint."
  default     = "172.16.0.0/28"
}

variable "machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "node_initial_count" {
  type    = number
  default = 2
}

variable "node_min_count" {
  type    = number
  default = 2
}

variable "node_max_count" {
  type    = number
  default = 4
}

variable "node_disk_size_gb" {
  type    = number
  default = 50
}

variable "labels" {
  type    = map(string)
  default = {}
}
