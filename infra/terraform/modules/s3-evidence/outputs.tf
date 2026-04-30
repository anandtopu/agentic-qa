output "bucket_name" {
  value = aws_s3_bucket.evidence.id
}

output "bucket_arn" {
  value = aws_s3_bucket.evidence.arn
}

output "kms_key_arn" {
  value = aws_kms_key.evidence.arn
}
