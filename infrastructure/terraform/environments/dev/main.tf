terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    # Configure this based on your setup
    # bucket = "your-terraform-state-bucket"
    # key    = "narrative-modeling/dev/terraform.tfstate"
    # region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "narrative-modeling-app"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

variable "environment" {
  default = "dev"
}

variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "narrative-modeling"
}

variable "mongodb_uri" {
  type      = string
  sensitive = true
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "clerk_secret_key" {
  type      = string
  sensitive = true
}

variable "clerk_webhook_secret" {
  type      = string
  sensitive = true
}

variable "datadog_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

module "networking" {
  source = "../../modules/networking"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
  enable_nat_gateway = false # Save costs in dev
}

module "storage" {
  source = "../../modules/storage"

  project_name         = var.project_name
  environment          = var.environment
  cors_allowed_origins = ["http://localhost:3000"]
  enable_cloudfront    = false # Save costs in dev
}

module "secrets" {
  source = "../../modules/secrets"

  project_name         = var.project_name
  environment          = var.environment
  mongodb_uri          = var.mongodb_uri
  openai_api_key       = var.openai_api_key
  clerk_secret_key     = var.clerk_secret_key
  clerk_webhook_secret = var.clerk_webhook_secret
  datadog_api_key      = var.datadog_api_key
}

module "ecs" {
  source = "../../modules/ecs"

  project_name                = var.project_name
  environment                 = var.environment
  vpc_id                      = module.networking.vpc_id
  public_subnet_ids           = module.networking.public_subnet_ids
  private_subnet_ids          = module.networking.private_subnet_ids
  alb_security_group_id       = module.networking.alb_security_group_id
  app_security_group_id       = module.networking.app_security_group_id
  data_bucket_name            = module.storage.data_bucket_name
  data_bucket_arn             = module.storage.data_bucket_arn
  aws_region                  = var.aws_region
  cors_origins                = ["http://localhost:3000"]
  mongodb_uri_secret_arn      = module.secrets.mongodb_uri_secret_arn
  openai_api_key_secret_arn   = module.secrets.openai_api_key_secret_arn
  clerk_secret_key_secret_arn = module.secrets.clerk_secret_key_secret_arn
  
  # Dev-specific settings
  backend_cpu           = 256
  backend_memory        = 512
  backend_desired_count = 1
  backend_min_count     = 1
  backend_max_count     = 2
  log_retention_days    = 3
}