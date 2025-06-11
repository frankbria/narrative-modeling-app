output "mongodb_uri_secret_arn" {
  description = "ARN of MongoDB URI secret"
  value       = aws_secretsmanager_secret.mongodb_uri.arn
}

output "openai_api_key_secret_arn" {
  description = "ARN of OpenAI API key secret"
  value       = aws_secretsmanager_secret.openai_api_key.arn
}

output "clerk_secret_key_secret_arn" {
  description = "ARN of Clerk secret key secret"
  value       = aws_secretsmanager_secret.clerk_secret_key.arn
}

output "clerk_webhook_secret_arn" {
  description = "ARN of Clerk webhook secret"
  value       = aws_secretsmanager_secret.clerk_webhook_secret.arn
}

output "datadog_api_key_secret_arn" {
  description = "ARN of Datadog API key secret"
  value       = var.datadog_api_key != "" ? aws_secretsmanager_secret.datadog_api_key[0].arn : null
}

output "secrets_read_policy_arn" {
  description = "ARN of the policy for reading secrets"
  value       = aws_iam_policy.secrets_read.arn
}