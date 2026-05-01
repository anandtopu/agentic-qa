variable "project_name" {
  type    = string
  default = "aqao"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "eks_kubernetes_version" {
  type    = string
  default = "1.30"
}

variable "db_username" {
  type    = string
  default = "aqao"
}

variable "db_password" {
  type      = string
  sensitive = true
}
