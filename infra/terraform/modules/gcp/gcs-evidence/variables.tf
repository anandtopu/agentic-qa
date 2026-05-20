variable "project_name" { type = string }
variable "environment" { type = string }

variable "location" {
  type        = string
  description = "Bucket + key-ring location (region or multi-region, e.g. US)."
  default     = "US"
}

variable "bucket_name" {
  type        = string
  description = "Override the auto-generated bucket name. Must be globally unique."
  default     = null
}

variable "kms_rotation_period" {
  type        = string
  description = "CMEK rotation period (seconds, e.g. 7776000s = 90 days)."
  default     = "7776000s"
}

variable "labels" {
  type    = map(string)
  default = {}
}
