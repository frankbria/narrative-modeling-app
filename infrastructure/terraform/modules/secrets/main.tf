# Secrets Management Module

# MongoDB URI Secret
resource "aws_secretsmanager_secret" "mongodb_uri" {
  name = "${var.project_name}-${var.environment}-mongodb-uri"
  
  tags = {
    Name        = "${var.project_name}-${var.environment}-mongodb-uri"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "mongodb_uri" {
  secret_id     = aws_secretsmanager_secret.mongodb_uri.id
  secret_string = var.mongodb_uri
}

# OpenAI API Key Secret
resource "aws_secretsmanager_secret" "openai_api_key" {
  name = "${var.project_name}-${var.environment}-openai-api-key"
  
  tags = {
    Name        = "${var.project_name}-${var.environment}-openai-api-key"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}

# Clerk Secret Key
resource "aws_secretsmanager_secret" "clerk_secret_key" {
  name = "${var.project_name}-${var.environment}-clerk-secret-key"
  
  tags = {
    Name        = "${var.project_name}-${var.environment}-clerk-secret-key"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "clerk_secret_key" {
  secret_id     = aws_secretsmanager_secret.clerk_secret_key.id
  secret_string = var.clerk_secret_key
}

# Clerk Webhook Secret
resource "aws_secretsmanager_secret" "clerk_webhook_secret" {
  name = "${var.project_name}-${var.environment}-clerk-webhook-secret"
  
  tags = {
    Name        = "${var.project_name}-${var.environment}-clerk-webhook-secret"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "clerk_webhook_secret" {
  secret_id     = aws_secretsmanager_secret.clerk_webhook_secret.id
  secret_string = var.clerk_webhook_secret
}

# Datadog API Key (if provided)
resource "aws_secretsmanager_secret" "datadog_api_key" {
  count = var.datadog_api_key != "" ? 1 : 0
  name  = "${var.project_name}-${var.environment}-datadog-api-key"
  
  tags = {
    Name        = "${var.project_name}-${var.environment}-datadog-api-key"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "datadog_api_key" {
  count         = var.datadog_api_key != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.datadog_api_key[0].id
  secret_string = var.datadog_api_key
}

# IAM policy for reading secrets
resource "aws_iam_policy" "secrets_read" {
  name        = "${var.project_name}-${var.environment}-secrets-read"
  description = "Policy to read secrets from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.mongodb_uri.arn,
          aws_secretsmanager_secret.openai_api_key.arn,
          aws_secretsmanager_secret.clerk_secret_key.arn,
          aws_secretsmanager_secret.clerk_webhook_secret.arn
        ]
      }
    ]
  })
}