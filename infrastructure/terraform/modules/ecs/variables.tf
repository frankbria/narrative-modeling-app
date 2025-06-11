variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs"
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "ALB security group ID"
  type        = string
}

variable "app_security_group_id" {
  description = "Application security group ID"
  type        = string
}

variable "data_bucket_name" {
  description = "S3 data bucket name"
  type        = string
}

variable "data_bucket_arn" {
  description = "S3 data bucket ARN"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "backend_image" {
  description = "Backend Docker image"
  type        = string
  default     = "nginx:latest" # Placeholder
}

variable "frontend_image" {
  description = "Frontend Docker image"
  type        = string
  default     = "nginx:latest" # Placeholder
}

variable "backend_cpu" {
  description = "Backend CPU units"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Backend memory (MB)"
  type        = number
  default     = 1024
}

variable "backend_desired_count" {
  description = "Backend desired task count"
  type        = number
  default     = 2
}

variable "backend_min_count" {
  description = "Backend minimum task count"
  type        = number
  default     = 1
}

variable "backend_max_count" {
  description = "Backend maximum task count"
  type        = number
  default     = 4
}

variable "cors_origins" {
  description = "CORS allowed origins"
  type        = list(string)
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "mongodb_uri_secret_arn" {
  description = "ARN of MongoDB URI secret"
  type        = string
}

variable "openai_api_key_secret_arn" {
  description = "ARN of OpenAI API key secret"
  type        = string
}

variable "clerk_secret_key_secret_arn" {
  description = "ARN of Clerk secret key secret"
  type        = string
}