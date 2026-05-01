variable "project_name" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "db_subnet_group_name" { type = string }

variable "client_security_group_ids" {
  type        = list(string)
  description = "Security groups allowed to connect on 5432 (typically EKS node SG)."
}

variable "instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "allocated_storage_gb" {
  type    = number
  default = 50
}

variable "max_allocated_storage_gb" {
  type    = number
  default = 200
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

variable "multi_az" {
  type    = bool
  default = false
}

variable "backup_retention_days" {
  type        = number
  description = "Days of automated backups to keep. PITR window matches this."
  default     = 7
}

variable "tags" {
  type    = map(string)
  default = {}
}
