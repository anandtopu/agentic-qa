variable "project_name" { type = string }
variable "environment" { type = string }

variable "bucket_name" {
  type        = string
  description = "Override the auto-generated bucket name. Must be globally unique."
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}
