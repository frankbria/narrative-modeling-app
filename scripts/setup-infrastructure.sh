#!/bin/bash
set -e

echo "Setting up infrastructure for Narrative Modeling App"
echo ""

# Check prerequisites
if ! command -v aws &> /dev/null; then
    echo "ERROR: aws CLI is not installed."
    echo ""
    echo "To install AWS CLI v2:"
    echo "  1. Download from: https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
    echo "  2. Or use the install script in scripts/aws/install"
    echo ""
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo "ERROR: terraform is not installed. Please install it first."
    exit 1
fi

echo "OK: All prerequisites installed"
echo ""

# Check AWS credentials
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "ERROR: AWS credentials not configured. Please run 'aws configure'"
    exit 1
fi
echo "OK: AWS credentials configured"
echo ""

# Create ECR repositories
echo "Creating ECR repositories..."
aws ecr create-repository --repository-name narrative-modeling-backend 2>/dev/null || echo "Backend repo exists"
aws ecr create-repository --repository-name narrative-modeling-frontend 2>/dev/null || echo "Frontend repo exists"
echo "OK: ECR repositories ready"
echo ""

# Initialize Terraform
echo "Initializing Terraform..."
cd infrastructure/terraform/environments/dev

if [ ! -f terraform.tfvars ]; then
    echo ""
    echo "WARNING: terraform.tfvars not found!"
    echo "Please create it from the example:"
    echo "  cp terraform.tfvars.example terraform.tfvars"
    echo "  vi terraform.tfvars"
    echo ""
    exit 1
fi

terraform init

echo ""
echo "Infrastructure setup complete!"
echo ""
echo "Next steps:"
echo "1. Review the Terraform plan:"
echo "   terraform plan"
echo ""
echo "2. Apply the infrastructure:"
echo "   terraform apply"
echo ""