variable "project_id" {
  type        = string
  description = "GCP project ID to deploy into."
}

variable "project_name" {
  type    = string
  default = "aqao"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "subnet_cidr" {
  type    = string
  default = "10.42.0.0/20"
}

variable "pods_cidr" {
  type    = string
  default = "10.43.0.0/16"
}

variable "services_cidr" {
  type    = string
  default = "10.44.0.0/20"
}

variable "evidence_location" {
  type    = string
  default = "US"
}

variable "db_username" {
  type    = string
  default = "aqao"
}

variable "db_password" {
  type      = string
  sensitive = true
}
