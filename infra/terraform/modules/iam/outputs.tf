output "api_role_arn" {
  value       = aws_iam_role.api.arn
  description = "ARN to bind to the API service-account via the eks.amazonaws.com/role-arn annotation."
}
