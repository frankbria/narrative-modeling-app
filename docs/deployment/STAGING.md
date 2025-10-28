# Staging Deployment Guide

**Server**: 47.88.89.175
**Domain**: dev.briaanalytics.com
**Environment**: Staging (Pre-Production)
**Status**: ✅ **FULLY DEPLOYED** (as of 2025-10-23)
**Last Updated**: 2025-10-27

---

## Table of Contents

1. [Overview](#overview)
2. [Current Deployment Status](#current-deployment-status)
3. [Architecture](#architecture)
4. [MongoDB Configuration](#mongodb-configuration)
5. [Services and Ports](#services-and-ports)
6. [Deployment Process](#deployment-process)
7. [Service Management](#service-management)
8. [Monitoring and Maintenance](#monitoring-and-maintenance)
9. [Troubleshooting](#troubleshooting)
10. [Security](#security)

---

## Overview

The staging environment serves as a pre-production testing ground for integration testing, sprint demonstrations, and QA validation before production deployment.

**Key Characteristics**:
- Shared server hosting multiple services
- Custom port assignments to avoid conflicts
- Self-hosted MongoDB 7.0
- Redis 7-alpine for caching
- SSL via Let's Encrypt
- Backend runs as systemd service

---

## Current Deployment Status

### ✅ Successfully Deployed Services

| Service | Status | Version | Port | Access |
|---------|--------|---------|------|--------|
| **Frontend** | ✅ Running | Next.js | 3010 | https://dev.briaanalytics.com |
| **Backend** | ✅ Running | FastAPI | 8010 | https://dev.briaanalytics.com/api |
| **MongoDB** | ✅ Healthy | 7.0 | 27018 | Docker container (self-hosted) |
| **Redis** | ✅ Healthy | 7-alpine | 6381 | Docker container |
| **Nginx** | ✅ Running | - | 80/443 | Reverse proxy |
| **SSL** | ✅ Valid | Let's Encrypt | - | Expires 2026-01-21 |

### Deployment Details

- **Deployment Date**: October 23, 2025
- **Location**: `/opt/narrative-modeling-app/staging`
- **User**: `narrative-deploy`
- **Backend Runtime**: Systemd service (`narrative-backend.service`)
- **Auto-start**: Enabled (starts on boot)

---

## Architecture

```
Internet (HTTPS)
    ↓
Nginx (80/443) - dev.briaanalytics.com
    ↓
    ├─→ Frontend (3010)
    └─→ Backend (8010)
             ↓
         ┌───┴───┬───────┐
         ↓       ↓       ↓
    MongoDB   Redis   AWS S3
    (27018)  (6381)
```

### Key Design Decisions

1. **Shared Server**: 47.88.89.175 hosts multiple applications, requiring custom ports
2. **Backend as Service**: systemd ensures reliability and proper environment variable loading
3. **Self-Hosted Database**: MongoDB 7.0 runs in Docker for development/staging use
4. **SSL Termination**: Nginx handles SSL, internal services use HTTP

---

## MongoDB Configuration

### Deployment Strategy

**Staging Environment**: Self-Hosted MongoDB in Docker

- **Version**: MongoDB 7.0
- **Container**: `narrative-staging-mongodb`
- **Port**: 27018 (custom to avoid conflicts)
- **Database**: `narrative_staging`
- **Status**: Running and healthy
- **Features**:
  - Persistent volume for data storage
  - Authentication enabled
  - Accessible via localhost from backend

### Connection String

The connection string is stored in `/opt/narrative-modeling-app/staging/.env.staging`:

```bash
MONGODB_URI=mongodb://narrative_user:PASSWORD@localhost:27018/narrative_staging?authSource=admin
MONGODB_DB=narrative_staging
```

**Format**:
```
mongodb://username:password@localhost:27018/narrative_staging?authSource=admin
```

### Docker Configuration

The MongoDB container is managed via Docker Compose (`docker-compose.simple.yml`):

```yaml
mongodb:
  image: mongo:7.0
  container_name: narrative-staging-mongodb
  ports:
    - "27018:27017"  # Custom external port to avoid conflicts
  environment:
    MONGO_INITDB_ROOT_USERNAME: root
    MONGO_INITDB_ROOT_PASSWORD: ${MONGODB_ROOT_PASSWORD}
    MONGO_INITDB_DATABASE: narrative_staging
  volumes:
    - mongodb_data:/data/db
  restart: unless-stopped
```

### MongoDB Management

**Connect via mongosh** (from staging server):
```bash
docker exec -it narrative-staging-mongodb mongosh \
  --username narrative_user \
  --password "${MONGODB_PASSWORD}" \
  --authenticationDatabase admin \
  narrative_staging
```

**Check Container Status**:
```bash
docker ps | grep mongodb
docker logs narrative-staging-mongodb --tail 100
```

**Backup Strategy**:
- Manual backups using mongodump
- Recommended: Daily automated backups to S3
- Data persisted in Docker volume: `mongodb_data`

---

## Services and Ports

### Port Allocation

The staging server (47.88.89.175) hosts multiple services. Custom ports avoid conflicts:

| Service | Default Port | Staging Port | Reason |
|---------|--------------|--------------|--------|
| Frontend | 3000 | **3010** | Ports 3000-3003 occupied |
| Backend | 8000 | **8010** | Ports 8000-8001 occupied |
| Redis | 6379 | **6381** | Port 6379 occupied |

**Note**: MongoDB runs on Atlas (managed cloud) and does not require a local port.

### Service Files

**Backend Systemd Service**: `/etc/systemd/system/narrative-backend.service`

```ini
[Unit]
Description=Narrative Modeling Backend
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=narrative-deploy
WorkingDirectory=/opt/narrative-modeling-app/staging/apps/backend
EnvironmentFile=/opt/narrative-modeling-app/staging/.env.staging
ExecStart=/usr/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8010
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Deployment Process

### Prerequisites

- SSH access to `47.88.89.175` as `narrative-deploy` user
- Docker and Docker Compose installed
- Environment variables configured in `.env.staging`
- GitHub repository access

### Initial Deployment (Already Complete)

The staging environment has been deployed. For reference, the initial deployment process was:

1. Created deployment user (`narrative-deploy`)
2. Installed Docker Compose plugin
3. Cloned repository to `/opt/narrative-modeling-app/staging`
4. Generated secrets and created `.env.staging`
5. Built and started services with `docker-compose.staging.yml`
6. Created systemd service for backend
7. Configured nginx reverse proxy
8. Set up SSL with Let's Encrypt

### Updating Deployed Application

```bash
# SSH as narrative-deploy user
ssh narrative-deploy@47.88.89.175

# Navigate to deployment directory
cd /opt/narrative-modeling-app/staging

# Pull latest code
git pull origin main

# Rebuild frontend (if needed)
cd apps/frontend
npm install
npm run build

# Restart backend service
sudo systemctl restart narrative-backend

# Restart database services (if needed)
cd /opt/narrative-modeling-app/staging
docker compose -f docker-compose.simple.yml restart

# Check service status
sudo systemctl status narrative-backend
docker compose -f docker-compose.simple.yml ps
```

---

## Service Management

### Backend Service (Systemd)

**Start/Stop/Restart**:
```bash
sudo systemctl start narrative-backend
sudo systemctl stop narrative-backend
sudo systemctl restart narrative-backend
```

**Check Status**:
```bash
sudo systemctl status narrative-backend
```

**View Logs**:
```bash
# Follow logs in real-time
journalctl -u narrative-backend -f

# Last 100 lines
journalctl -u narrative-backend -n 100

# Since specific time
journalctl -u narrative-backend --since "1 hour ago"
```

**Enable/Disable Auto-start**:
```bash
sudo systemctl enable narrative-backend   # Start on boot
sudo systemctl disable narrative-backend  # Don't start on boot
```

### Database Services (Docker Compose)

```bash
# Navigate to deployment directory
cd /opt/narrative-modeling-app/staging

# View running containers
docker compose -f docker-compose.simple.yml ps

# View logs
docker compose -f docker-compose.simple.yml logs -f

# Restart services
docker compose -f docker-compose.simple.yml restart

# Stop services
docker compose -f docker-compose.simple.yml down

# Start services
docker compose -f docker-compose.simple.yml up -d
```

---

## Monitoring and Maintenance

### Health Checks

**Backend API**:
```bash
curl https://dev.briaanalytics.com/api/health
# Expected: {"status": "healthy"}
```

**Frontend**:
```bash
curl -I https://dev.briaanalytics.com
# Expected: HTTP/2 200
```

**Direct Access (Internal)**:
```bash
curl http://localhost:8010/health  # Backend
curl http://localhost:3010          # Frontend
```

### Resource Monitoring

**System Resources**:
```bash
# Memory usage
free -h

# Disk usage
df -h /opt/narrative-modeling-app

# CPU usage
top
```

**Docker Resources**:
```bash
# Container resource usage
docker stats

# Specific container
docker stats narrative-staging-mongodb
```

### Log Rotation

Backend logs are managed by systemd journal rotation. Database logs are managed by Docker.

**Configure Journal Retention** (if needed):
```bash
# Edit journald configuration
sudo nano /etc/systemd/journald.conf

# Set max retention
SystemMaxUse=500M
MaxRetentionSec=7day

# Restart journald
sudo systemctl restart systemd-journald
```

---

## Troubleshooting

### Backend Won't Start

```bash
# Check service status
sudo systemctl status narrative-backend

# Check logs for errors
journalctl -u narrative-backend -n 50

# Verify environment variables
sudo cat /opt/narrative-modeling-app/staging/.env.staging | grep -v PASSWORD

# Test backend manually
cd /opt/narrative-modeling-app/staging/apps/backend
source /opt/narrative-modeling-app/staging/.env.staging
uv run uvicorn app.main:app --host 127.0.0.1 --port 8011
```

### MongoDB Connection Issues

```bash
# Check MongoDB is running
docker ps | grep mongodb

# Test MongoDB connection
docker exec narrative-staging-mongodb mongosh \
  --username narrative_user \
  --password "${MONGODB_PASSWORD}" \
  --authenticationDatabase admin \
  narrative_staging \
  --eval "db.runCommand({ping: 1})"

# Check MongoDB logs
docker logs narrative-staging-mongodb --tail 100
```

### Nginx/SSL Issues

```bash
# Test nginx configuration
sudo nginx -t

# Check nginx error logs
sudo tail -f /var/log/nginx/narrative-staging-error.log

# Verify SSL certificate
sudo certbot certificates

# Renew SSL (if needed)
sudo certbot renew --dry-run
```

### Frontend Build Issues

```bash
cd /opt/narrative-modeling-app/staging/apps/frontend

# Check Node.js version
node --version

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Build manually
npm run build
```

---

## Security

### Current Security Measures

- ✅ SSL/TLS enabled via Let's Encrypt
- ✅ MongoDB authentication required
- ✅ Redis password protected
- ✅ Backend secret key configured
- ✅ UFW firewall configured
- ✅ Non-root user for application
- ✅ Environment variables secured (600 permissions)
- ✅ Auto-renewal for SSL certificates

### Secrets Management

**IMPORTANT**: All secrets are stored securely in `/opt/narrative-modeling-app/staging/.env.staging` on the staging server. These secrets should NEVER be committed to version control.

Required secrets:
- `MONGODB_ROOT_PASSWORD` - MongoDB admin password
- `MONGODB_PASSWORD` - MongoDB application user password
- `REDIS_PASSWORD` - Redis authentication password
- `BACKEND_SECRET_KEY` - FastAPI secret key (64 chars)
- `NEXTAUTH_SECRET` - NextAuth authentication secret (64 chars)

To generate new secrets if needed:
```bash
# Generate strong passwords
openssl rand -base64 32

# Generate hex keys
openssl rand -hex 32
```

### Security Best Practices

1. **Regular Updates**:
   ```bash
   # System updates
   sudo apt update && sudo apt upgrade -y

   # Docker images
   docker compose -f docker-compose.simple.yml pull
   docker compose -f docker-compose.simple.yml up -d
   ```

2. **Backup Strategy**:
   - Daily MongoDB dumps
   - Weekly full backups
   - Store backups off-server (S3 or similar)

3. **Access Control**:
   - Use SSH keys (disable password auth)
   - Limit sudo access
   - Audit user access regularly

4. **Monitoring**:
   - Set up log monitoring
   - Configure alerts for service failures
   - Monitor resource usage

---

## Quick Reference

### Common Commands

```bash
# Check all services
sudo systemctl status narrative-backend
docker compose -f docker-compose.simple.yml ps

# Restart everything
sudo systemctl restart narrative-backend
docker compose -f docker-compose.simple.yml restart

# View logs
journalctl -u narrative-backend -f
docker compose -f docker-compose.simple.yml logs -f

# Update application
cd /opt/narrative-modeling-app/staging
git pull origin main
cd apps/frontend && npm install && npm run build
sudo systemctl restart narrative-backend
```

### Contact Information

- **Server**: 47.88.89.175
- **Domain**: https://dev.briaanalytics.com
- **SSH User**: narrative-deploy
- **Deployment Path**: `/opt/narrative-modeling-app/staging`

---

**Document Status**: Current and Accurate
**Last Verified**: 2025-10-27
**Deployment Status**: ✅ Production-Ready Staging Environment
