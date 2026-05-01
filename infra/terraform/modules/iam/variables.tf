variable "project_name" { type = string }
variable "environment" { type = string }
variable "oidc_provider_arn" { type = string }
variable "oidc_provider_url" { type = string }

variable "namespace" {
  type        = string
  description = "Kubernetes namespace where the API service account lives."
  default     = "aqao"
}

variable "service_account_name" {
  type    = string
  default = "aqao-api"
}

variable "secret_arns" {
  type        = map(string)
  description = "Map of secret name -> ARN, output of the secrets module."
}

variable "evidence_bucket_arn" { type = string }
variable "evidence_kms_key_arn" { type = string }

variable "tags" {
  type    = map(string)
  default = {}
}
