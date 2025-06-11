#!/bin/bash
# Quick development startup script

set -e

echo "Starting Narrative Modeling App (Local Development)"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Run: cp .env.example .env"
    echo "Then add your API keys"
    exit 1
fi

# Check if MongoDB and LocalStack are running
if ! docker compose ps | grep -q narrative-mongodb; then
    echo "Starting infrastructure services..."
    docker compose up -d mongodb localstack
    sleep 5
    
    # Create S3 bucket
    docker compose exec -T localstack awslocal s3 mb s3://narrative-modeling-local 2>/dev/null || true
fi

# Option to run with Docker or locally
if [ "$1" = "--docker" ]; then
    echo "Starting with Docker Compose..."
    docker compose up backend frontend
else
    echo "Starting services locally..."
    echo ""
    echo "Make sure you have:"
    echo "1. MongoDB running on localhost:27017"
    echo "2. Set up your Python environment in apps/backend"
    echo "3. Installed Node dependencies in apps/frontend"
    echo ""
    echo "Start backend:"
    echo "  cd apps/backend"
    echo "  source .venv/bin/activate"
    echo "  uvicorn app.main:app --reload"
    echo ""
    echo "Start frontend (new terminal):"
    echo "  cd apps/frontend" 
    echo "  npm run dev"
fi