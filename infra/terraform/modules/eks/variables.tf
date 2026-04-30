variable "project_name" { type = string }
variable "environment" { type = string }

variable "cluster_name" {
  type        = string
  description = "EKS cluster name. Must match the value used in vpc/cluster_name."
}

variable "kubernetes_version" {
  type        = string
  description = "Kubernetes minor version (e.g. '1.30')."
  default     = "1.30"
}

variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }

variable "public_access_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to hit the EKS API server endpoint."
  default     = ["0.0.0.0/0"]
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 6
}

variable "tags" {
  type    = map(string)
  default = {}
}
