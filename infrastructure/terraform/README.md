# Terraform Infrastructure

This directory contains the Terraform configuration for the Narrative Modeling App infrastructure.

## Structure

```
terraform/
├── modules/           # Reusable Terraform modules
│   ├── networking/   # VPC, subnets, security groups
│   ├── storage/      # S3 buckets, CloudFront
│   ├── ecs/          # ECS cluster, services, ALB
│   └── secrets/      # AWS Secrets Manager
├── environments/      # Environment-specific configurations
│   ├── dev/
│   ├── staging/
│   └── prod/
└── README.md
```

## Prerequisites

1. **AWS Account**: You need an AWS account with appropriate permissions
2. **Terraform**: Version 1.5 or higher
3. **AWS CLI**: Configured with your credentials
4. **S3 Backend Bucket**: For storing Terraform state (optional but recommended)

## Quick Start

### 1. Set up AWS credentials

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter your default region (e.g., us-east-1)
```

### 2. Create a terraform.tfvars file

```bash
cd environments/dev
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your actual values
```

### 3. Initialize Terraform

```bash
terraform init
```

### 4. Plan the infrastructure

```bash
terraform plan
```

### 5. Apply the infrastructure

```bash
terraform apply
```

## Environment Variables Required

- `mongodb_uri`: MongoDB connection string
- `openai_api_key`: OpenAI API key
- `clerk_secret_key`: Clerk authentication secret
- `clerk_webhook_secret`: Clerk webhook secret
- `datadog_api_key`: (Optional) Datadog monitoring

## Outputs

After applying, you'll get:
- `alb_dns_name`: The URL to access your application
- `data_bucket_name`: S3 bucket for data storage
- `ecs_cluster_name`: ECS cluster name for deployments

## Cost Optimization

### Development Environment
- NAT Gateway disabled (uses public IPs)
- Minimal ECS tasks (1 backend, 1 frontend)
- No CloudFront distribution
- Shorter log retention

### Production Environment
- NAT Gateway enabled for security
- Auto-scaling enabled
- CloudFront for static assets
- Longer log retention

## Destroying Infrastructure

To tear down the infrastructure:

```bash
terraform destroy
```

## Troubleshooting

### Common Issues

1. **Insufficient IAM permissions**
   - Ensure your AWS user has permissions for: VPC, ECS, S3, Secrets Manager, IAM

2. **Resource already exists**
   - Check if resources were created manually
   - Use different names in terraform.tfvars

3. **ECS tasks not starting**
   - Check CloudWatch logs
   - Verify secrets are correctly set
   - Ensure Docker images exist in ECR

## Security Best Practices

1. **Never commit secrets**: Use terraform.tfvars and add to .gitignore
2. **Use least privilege**: IAM roles have minimal required permissions
3. **Enable encryption**: S3 buckets and secrets are encrypted
4. **Private subnets**: Applications run in private subnets (production)
5. **Security groups**: Restrict access to necessary ports only