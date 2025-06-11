#!/bin/bash

# Production Deployment Script for Narrative Modeling App
set -e

echo "🚀 Starting Production Deployment..."

# Configuration
ENVIRONMENT="production"
DOCKER_COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if environment file exists
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file $ENV_FILE not found. Please create it from .env.production.example"
        exit 1
    fi
    
    log_info "Prerequisites check passed ✓"
}

# Backup current deployment
backup_current() {
    log_info "Creating backup of current deployment..."
    
    if [ -f "$DOCKER_COMPOSE_FILE" ]; then
        # Export current volumes
        docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T mongodb mongodump --archive > "backup/mongodb_$(date +%Y%m%d_%H%M%S).archive" || true
        log_info "Database backup completed ✓"
    fi
}

# Build images
build_images() {
    log_info "Building Docker images..."
    
    # Build with no cache for production
    docker-compose -f "$DOCKER_COMPOSE_FILE" build --no-cache
    
    log_info "Docker images built successfully ✓"
}

# Deploy services
deploy_services() {
    log_info "Deploying services..."
    
    # Create backup directory
    mkdir -p backup
    
    # Stop existing services
    docker-compose -f "$DOCKER_COMPOSE_FILE" down --remove-orphans || true
    
    # Start new services
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d
    
    log_info "Services deployed successfully ✓"
}

# Health checks
check_health() {
    log_info "Performing health checks..."
    
    # Wait for services to start
    sleep 30
    
    # Check backend health
    max_attempts=30
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost/api/health > /dev/null 2>&1; then
            log_info "Backend health check passed ✓"
            break
        else
            if [ $attempt -eq $max_attempts ]; then
                log_error "Backend health check failed after $max_attempts attempts"
                exit 1
            fi
            log_warn "Attempt $attempt/$max_attempts: Backend not ready, waiting..."
            sleep 10
            ((attempt++))
        fi
    done
    
    # Check frontend health
    if curl -f http://localhost > /dev/null 2>&1; then
        log_info "Frontend health check passed ✓"
    else
        log_error "Frontend health check failed"
        exit 1
    fi
    
    log_info "All health checks passed ✓"
}

# Database migration
run_migrations() {
    log_info "Running database migrations..."
    
    # Run any pending migrations
    docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T backend uv run python -c "
import asyncio
from app.db.mongodb import connect_to_mongo
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def migrate():
    mongo_uri = os.getenv('MONGODB_URI')
    db_name = os.getenv('MONGODB_DB')
    client = AsyncIOMotorClient(mongo_uri)
    
    # Import all models
    from app.models.user_data import UserData
    from app.models.analytics_result import AnalyticsResult
    from app.models.plot import Plot
    from app.models.trained_model import TrainedModel
    from app.models.column_stats import ColumnStats
    from app.models.ml_model import MLModel
    from app.models.api_key import APIKey
    from app.models.ab_test import ABTest
    from app.models.batch_job import BatchJob
    
    await init_beanie(
        database=client[db_name],
        document_models=[UserData, AnalyticsResult, Plot, TrainedModel, ColumnStats, MLModel, APIKey, ABTest, BatchJob],
    )
    
    print('Database migration completed')

asyncio.run(migrate())
" || true
    
    log_info "Database migrations completed ✓"
}

# Cleanup old images
cleanup() {
    log_info "Cleaning up old Docker images..."
    
    # Remove unused images
    docker image prune -f || true
    
    # Remove dangling volumes
    docker volume prune -f || true
    
    log_info "Cleanup completed ✓"
}

# Show deployment status
show_status() {
    log_info "Deployment Status:"
    echo
    docker-compose -f "$DOCKER_COMPOSE_FILE" ps
    echo
    
    log_info "Application URLs:"
    echo "  Frontend: http://localhost"
    echo "  Backend API: http://localhost/api"
    echo "  Health Check: http://localhost/health"
    echo
    
    log_info "View logs with:"
    echo "  docker-compose -f $DOCKER_COMPOSE_FILE logs -f [service_name]"
}

# Rollback function
rollback() {
    log_warn "Rolling back deployment..."
    
    # Stop current services
    docker-compose -f "$DOCKER_COMPOSE_FILE" down
    
    # Restore from backup if available
    latest_backup=$(ls -t backup/mongodb_*.archive 2>/dev/null | head -n1)
    if [ -n "$latest_backup" ]; then
        log_info "Restoring database from $latest_backup"
        docker-compose -f "$DOCKER_COMPOSE_FILE" up -d mongodb
        sleep 10
        docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T mongodb mongorestore --archive < "$latest_backup"
    fi
    
    log_warn "Rollback completed. Please check your previous deployment."
}

# Main deployment process
main() {
    # Parse command line arguments
    case "${1:-}" in
        "rollback")
            rollback
            exit 0
            ;;
        "status")
            show_status
            exit 0
            ;;
        "logs")
            docker-compose -f "$DOCKER_COMPOSE_FILE" logs -f "${2:-}"
            exit 0
            ;;
    esac
    
    # Trap errors and rollback
    trap 'log_error "Deployment failed! Run with rollback option to revert."; exit 1' ERR
    
    # Run deployment steps
    check_prerequisites
    backup_current
    build_images
    deploy_services
    run_migrations
    check_health
    cleanup
    show_status
    
    log_info "🎉 Production deployment completed successfully!"
    log_info "Monitor the application and check logs for any issues."
}

# Show usage information
usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  (no args)     Deploy the application"
    echo "  rollback      Rollback to previous deployment"
    echo "  status        Show current deployment status"
    echo "  logs [service] Show logs for all services or specific service"
    echo ""
    echo "Examples:"
    echo "  $0                    # Deploy the application"
    echo "  $0 status            # Show deployment status"
    echo "  $0 logs backend      # Show backend logs"
    echo "  $0 rollback          # Rollback deployment"
}

# Handle help option
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

# Execute main function
main "$@"