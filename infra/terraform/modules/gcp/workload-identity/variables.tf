variable "project_id" {
  type        = string
  description = "GCP project ID (for the cloudsql.client binding + WI member)."
}

variable "project_name" { type = string }
variable "environment" { type = string }

variable "namespace" {
  type        = string
  description = "Kubernetes namespace where the API service account lives."
  default     = "aqao"
}

variable "kubernetes_service_account" {
  type        = string
  description = "Name of the Kubernetes service account to bind (the Helm chart's KSA)."
  default     = "aqao-api"
}

variable "secret_ids" {
  type        = map(string)
  description = "Map of secret name -> secret id, from the secret-manager module."
}

variable "evidence_bucket_name" {
  type        = string
  description = "Evidence bucket name (module.evidence.bucket_name)."
}

variable "evidence_kms_key_id" {
  type        = string
  description = "Evidence CMEK key id (module.evidence.kms_key_id)."
}
