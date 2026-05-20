variable "project_name" { type = string }
variable "environment" { type = string }

variable "audit_hmac_key" {
  type      = string
  sensitive = true
  default   = null # null -> generate
}

variable "github_webhook_secret" {
  type      = string
  sensitive = true
  default   = null
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
  default   = null # null -> placeholder; rotate before any prod use
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "labels" {
  type    = map(string)
  default = {}
}
