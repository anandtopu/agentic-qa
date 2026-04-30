output "vpc_id" {
  value       = aws_vpc.this.id
  description = "ID of the VPC."
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "Public subnet IDs (one per AZ)."
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "Private (worker-node) subnet IDs."
}

output "database_subnet_ids" {
  value       = aws_subnet.database[*].id
  description = "RDS / ElastiCache subnet IDs."
}

output "db_subnet_group_name" {
  value       = aws_db_subnet_group.this.name
  description = "DB subnet group for the rds module."
}

output "azs" {
  value       = local.azs
  description = "Resolved AZ names."
}
