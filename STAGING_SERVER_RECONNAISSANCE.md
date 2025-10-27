# Staging Server Reconnaissance Results

**Server**: 47.88.89.175 (root access)
**Date**: 2025-10-22
**Status**: ✅ Reconnaissance Complete

---

## System Information

### Operating System
- **OS**: Ubuntu 24.04.3 LTS (Noble Numbat)
- **Kernel**: Linux

### Resources
- **Disk Space**: 232GB total, 35GB used, 197GB available (16% used) ✅
- **Memory**: 16GB total, 3.4GB used, 11GB available ✅
- **Swap**: None configured

### Docker Environment
- **Docker Version**: 28.2.2 ✅
- **Docker Compose**: ❌ **NOT INSTALLED** - Need to install `docker-compose-plugin`

---

## Port Allocation Analysis

### Currently Occupied Ports

| Port  | Service                    | Status |
|-------|----------------------------|--------|
| 22    | SSH                        | System |
| 53    | systemd-resolved (DNS)     | System |
| 80    | nginx (HTTP)               | Web Server |
| 443   | nginx (HTTPS)              | Web Server |
| 1337  | Node.js service            | App |
| 3000  | next-server                | App |
| 3001  | next-server                | App |
| 3002  | next-server                | App |
| 3003  | next-server                | App |
| 3306  | MySQL (localhost only)     | Database |
| 5432  | PostgreSQL (localhost only)| Database |
| 6379  | Redis (localhost only)     | Cache |
| 8000  | Python/FastAPI             | App |
| 8001  | Python/FastAPI             | App |
| 8080  | Docker proxy (nginx)       | Container |

### Assigned Ports for Narrative Modeling App (Staging)

| Service          | Default Port | Staging Port | Reason |
|------------------|--------------|--------------|--------|
| **Frontend**     | 3000         | **3010**     | 3000-3003 occupied |
| **Backend**      | 8000         | **8010**     | 8000-8001 occupied |
| **MongoDB**      | 27017        | **27018**    | Standard practice (avoid conflicts) |
| **Redis**        | 6379         | **6381**     | 6379 occupied (localhost) |
| **Nginx Proxy**  | 80/443       | **Use existing nginx** | Configure subdomain routing |

**Port Range Reserved**: 3010, 8010, 27018, 6381

---

## Existing Docker Containers

Currently running containers (SprintForge project):

| Container | Image | Status | Ports |
|-----------|-------|--------|-------|
| sprintforge-staging-frontend | sprintforge-frontend | Up 3 days (unhealthy) | 3000/tcp |
| sprintforge-cloudflared | cloudflare/cloudflared | Restarting | - |
| sprintforge-staging-nginx | nginx:alpine | Up 3 days (unhealthy) | 8080:80 |
| sprintforge-staging-backend | sprintforge-backend | Up 3 days (healthy) | 8000/tcp |
| sprintforge-staging-db | postgres:15-alpine | Up 3 days (healthy) | 5432/tcp |
| sprintforge-staging-redis | redis:7-alpine | Up 3 days (healthy) | 6379/tcp |
| sprintforge-watchtower | containrrr/watchtower | Up 3 days (healthy) | 8080/tcp |

**Notes**:
- SprintForge project uses internal networking (no port conflicts expected)
- Narrative Modeling App will use separate Docker network
- No MongoDB container running (need to deploy)

---

## Network Architecture

### Existing Setup
```
Internet → Nginx (80/443)
             ↓
   ┌─────────┴─────────┐
   │                   │
SprintForge Apps    (Available for new apps)
```

### Proposed Narrative Modeling App Setup
```
Internet → Nginx (80/443)
             ↓
   subdomain: narrative.yourdomain.com (or path-based routing)
             ↓
   ┌─────────┴─────────┐
   │                   │
Frontend:3010      Backend:8010
                        ↓
              ┌─────────┴─────────┐
              │                   │
         MongoDB:27018        Redis:6381
```

---

## Required Actions

### Immediate (Before Deployment)

- [ ] **Install Docker Compose Plugin**
  ```bash
  ssh root@47.88.89.175
  apt-get update
  apt-get install docker-compose-plugin -y
  docker compose version  # Verify installation
  ```

- [ ] **Configure Nginx Subdomain/Path Routing**
  - Option A: Subdomain routing (e.g., `narrative.yourdomain.com`)
  - Option B: Path-based routing (e.g., `yourdomain.com/narrative`)
  - Requires nginx configuration update

- [ ] **Create Deployment User** (Security Best Practice)
  ```bash
  adduser narrative-deploy
  usermod -aG docker narrative-deploy
  # Setup SSH keys for deployment automation
  ```

- [ ] **Create Directory Structure**
  ```bash
  mkdir -p /opt/narrative-modeling-app/staging
  chown narrative-deploy:narrative-deploy /opt/narrative-modeling-app -R
  ```

### Security Considerations

- [ ] Configure firewall rules for new ports (3010, 8010, 27018, 6381)
- [ ] Set up MongoDB authentication (even on staging)
- [ ] Configure Redis password
- [ ] Generate staging SSL certificate (Let's Encrypt)
- [ ] Set up environment variables file (.env.staging)
- [ ] Configure log rotation for application logs

---

## Next Steps

1. **Install Docker Compose plugin** on staging server
2. **Choose nginx routing strategy** (subdomain vs path-based)
3. **Create `docker-compose.staging.yml`** with assigned ports
4. **Create `.env.staging.example`** template
5. **Configure nginx** for reverse proxy to port 3010
6. **Set up GitHub Actions deployment workflow**
7. **Deploy and test**

---

## Configuration Files to Create

1. `docker-compose.staging.yml` - Staging-specific Docker Compose with custom ports
2. `.env.staging.example` - Example environment variables
3. `nginx-staging.conf` - Nginx reverse proxy configuration
4. `.github/workflows/deploy-staging.yml` - Automated deployment workflow

---

**Last Updated**: 2025-10-22
**Status**: Reconnaissance complete, ready for deployment setup
