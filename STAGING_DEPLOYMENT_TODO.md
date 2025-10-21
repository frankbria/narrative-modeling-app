# Staging Deployment Setup - TODO

**Target Server**: 47.88.89.175 (root access)
**Current Status**: 🚧 Not configured
**Priority**: High (needed for Sprint 12+)

## Overview

This document outlines the steps needed to set up the staging deployment server for the Narrative Modeling App. The staging server will serve as an integration testing and demo environment before production deployment.

## Server Information

- **IP Address**: 47.88.89.175
- **Access**: SSH as root (`ssh root@47.88.89.175`)
- **Purpose**: Staging environment for integration testing and sprint demos
- **Constraint**: Server hosts multiple services - **default ports will conflict**

## Port Allocation Strategy

⚠️ **CRITICAL**: Default ports (80, 443, 5432, 27017, 6379, etc.) are likely in use.

### Required Services & Port Assignments

Need to identify free ports for:

1. **Frontend (Next.js)**
   - Default: 3000
   - Staging: TBD (scan for available port)

2. **Backend (FastAPI)**
   - Default: 8000
   - Staging: TBD (scan for available port)

3. **MongoDB**
   - Default: 27017
   - Staging: TBD (scan for available port)

4. **Redis**
   - Default: 6379
   - Staging: TBD (scan for available port)

5. **Nginx/Reverse Proxy** (if needed)
   - Default: 80, 443
   - Staging: May need custom port or subdomain routing

### Port Discovery Steps

```bash
# SSH into server
ssh root@47.88.89.175

# Check which ports are in use
netstat -tulpn | grep LISTEN
# or
ss -tulpn | grep LISTEN

# Check specific port availability
nc -zv localhost 3000  # Test if port 3000 is open

# List all Docker containers (if any)
docker ps -a
```

## Deployment Architecture

```
Internet
    ↓
47.88.89.175:[PROXY_PORT]
    ↓
[Nginx/Reverse Proxy]
    ↓
    ├─→ Frontend:[FRONTEND_PORT]
    └─→ Backend:[BACKEND_PORT]
             ↓
             ├─→ MongoDB:[MONGO_PORT]
             ├─→ Redis:[REDIS_PORT]
             └─→ S3 (AWS production or MinIO local)
```

## Pre-Deployment Tasks

### 1. Server Reconnaissance

- [ ] SSH into 47.88.89.175 as root
- [ ] Document existing services and port usage
- [ ] Check available disk space (`df -h`)
- [ ] Check available memory (`free -h`)
- [ ] Identify OS version (`lsb_release -a` or `cat /etc/os-release`)
- [ ] Check if Docker is installed (`docker --version`)
- [ ] Check if Docker Compose is installed (`docker compose version`)

### 2. Port Assignment

- [ ] Identify free ports for all services
- [ ] Document port mappings in config file
- [ ] Update application configs to use assigned ports

### 3. Environment Setup

- [ ] Create deployment user (avoid using root for app)
- [ ] Set up SSH keys for deployment automation
- [ ] Install/update Docker if needed
- [ ] Install/update Docker Compose if needed
- [ ] Configure firewall rules for assigned ports
- [ ] Set up log rotation
- [ ] Create directory structure for app deployment

### 4. Application Configuration

- [ ] Create staging environment variables file (`.env.staging`)
- [ ] Configure database connection strings with custom ports
- [ ] Configure Redis connection with custom port
- [ ] Set up S3/file storage configuration
- [ ] Configure application to use custom ports
- [ ] Set up SSL certificates (if using HTTPS)

### 5. Deployment Pipeline

- [ ] Create GitHub Actions workflow for staging deployment
- [ ] Set up deployment secrets in GitHub
- [ ] Configure post-deployment smoke tests
- [ ] Set up rollback mechanism
- [ ] Configure deployment notifications

### 6. Monitoring & Logging

- [ ] Set up application logging (centralized or local)
- [ ] Configure health check endpoints
- [ ] Set up basic monitoring (uptime, resource usage)
- [ ] Configure error alerting

## Deployment Workflow Design

### Proposed Flow

```yaml
# .github/workflows/deploy-staging.yml (to be created)

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  integration-tests:
    # Run integration tests first

  deploy-staging:
    needs: integration-tests
    if: success()
    steps:
      - Deploy to 47.88.89.175
      - Run smoke tests
      - Notify on success/failure
```

## Configuration Files to Create

1. **`docker-compose.staging.yml`** - Staging-specific Docker Compose
2. **`.env.staging.example`** - Example staging environment variables
3. **`nginx.staging.conf`** - Nginx config for staging (if used)
4. **`.github/workflows/deploy-staging.yml`** - Deployment workflow

## Security Considerations

- [ ] Use environment variables for sensitive data (no hardcoded secrets)
- [ ] Configure firewall to only expose necessary ports
- [ ] Use non-root user for running application
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Set up regular security updates
- [ ] Configure database authentication (even on staging)
- [ ] Implement rate limiting on API endpoints
- [ ] Set up basic intrusion detection/monitoring

## Success Criteria

Staging deployment is complete when:

- ✅ All services running on identified ports
- ✅ Frontend accessible via HTTP/HTTPS
- ✅ Backend API responding correctly
- ✅ Database connections working
- ✅ GitHub Actions can deploy automatically
- ✅ Smoke tests pass after deployment
- ✅ Monitoring and logging operational
- ✅ Rollback mechanism tested and working

## References

- Main deployment docs: [`DEPLOYMENT.md`](./DEPLOYMENT.md)
- Integration tests: [`.github/workflows/integration-tests.yml`](./.github/workflows/integration-tests.yml)
- Backend docs: [`apps/backend/docs/`](./apps/backend/docs/)

## Next Steps

1. **Immediate**: SSH into 47.88.89.175 and perform server reconnaissance
2. **Next**: Document port assignments and create configuration files
3. **Then**: Set up deployment workflow
4. **Finally**: Test end-to-end deployment process

---

**Created**: 2025-10-21
**Last Updated**: 2025-10-21
**Status**: Planning phase
