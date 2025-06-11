#!/bin/bash
set -e

echo "Setting up local development environment"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "IMPORTANT: Edit .env file with your API keys!"
    echo ""
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed"
    exit 1
fi

echo "Starting services..."
docker compose up -d mongodb localstack

echo "Waiting for services to be ready..."
sleep 5

# Create S3 bucket in LocalStack
echo "Creating local S3 bucket..."
docker compose exec -T localstack awslocal s3 mb s3://narrative-modeling-local || echo "Bucket exists"

echo ""
echo "Local infrastructure ready!"
echo ""
echo "Services running:"
echo "- MongoDB: localhost:27017"
echo "- LocalStack S3: localhost:4566"
echo ""
echo "To start the application:"
echo "  docker compose up"
echo ""
echo "Or run services individually:"
echo "  docker compose up backend"
echo "  docker compose up frontend"