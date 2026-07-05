# Staging Deployment Guide - Step by Step

**Server**: 47.88.89.175 (root access)
**Date Created**: 2025-10-22
**Status**: Ready for deployment

---

## Prerequisites Checklist

Before starting deployment, ensure you have:

- [ ] SSH access to 47.88.89.175 as root
- [ ] Domain name or subdomain configured (DNS pointing to 47.88.89.175)
- [ ] AWS S3 bucket created for staging uploads
- [ ] AWS IAM credentials with S3 access
- [ ] OpenAI API key
- [ ] Google OAuth credentials (optional)
- [ ] GitHub OAuth credentials (optional)

---

## Step 1: Install Docker Compose Plugin

```bash
ssh root@47.88.89.175

# Update package list
apt-get update

# Install Docker Compose plugin
apt-get install docker-compose-plugin -y

# Verify installation
docker compose version
# Expected: Docker Compose version v2.x.x
```

---

## Step 2: Create Deployment User (Security Best Practice)

```bash
# Create dedicated user for deployment
adduser narrative-deploy --disabled-password --gecos "Narrative Modeling Deployment"

# Add to docker group
usermod -aG docker narrative-deploy

# Create deployment directory
mkdir -p /opt/narrative-modeling-app/staging
chown -R narrative-deploy:narrative-deploy /opt/narrative-modeling-app

# Setup SSH key for GitHub Actions deployment (optional)
# Run this on your local machine:
# ssh-keygen -t ed25519 -C "github-actions-narrative-staging" -f ~/.ssh/narrative-staging
# Then add the public key to narrative-deploy user:
# su - narrative-deploy
# mkdir -p ~/.ssh && chmod 700 ~/.ssh
# echo "PASTE_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
# chmod 600 ~/.ssh/authorized_keys
```

---

## Step 3: Generate Secrets

```bash
# On your local machine or staging server, generate secrets:

# MongoDB: staging uses a managed MongoDB Atlas cluster — no local Mongo
# container or passwords. Get the mongodb+srv:// connection string from the
# Atlas UI (Database → Connect → Drivers) for MONGODB_URI.

# Redis password — hex, NOT base64: the password is embedded in a redis:// URL
# and base64's / + = characters break URL parsing
openssl rand -hex 32  # For REDIS_PASSWORD

# Backend secret key
openssl rand -hex 32  # For BACKEND_SECRET_KEY (64 chars)

# NextAuth secret
openssl rand -hex 32  # For NEXTAUTH_SECRET (64 chars)

# Save these in a secure password manager!
```

---

## Step 4: Create Environment Variables File

```bash
# SSH into staging server
ssh narrative-deploy@47.88.89.175

# Navigate to deployment directory
cd /opt/narrative-modeling-app/staging

# Create .env.staging file (based on .env.staging.example)
nano .env.staging

# Paste the following with actual values:
# (See .env.staging.example for full template)
```

**Required values**:
- `MONGODB_URI`: MongoDB Atlas connection string (`mongodb+srv://...`)
- `MONGODB_DB`: Staging database name (e.g. `narrative_modeling-staging`)
- `REDIS_PASSWORD`: Generated secret (do **not** set `REDIS_URL` — compose builds it)
- `AWS_ACCESS_KEY_ID`: Your AWS key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret
- `S3_BUCKET_NAME`: narrative-staging-uploads
- `OPENAI_API_KEY`: Your OpenAI key
- `BACKEND_SECRET_KEY`: Generated secret
- `NEXTAUTH_SECRET`: Generated secret
- `NEXT_PUBLIC_API_URL`: https://narrative.yourdomain.com/api/v1 (must include `/api/v1`)
- `NEXTAUTH_URL`: https://narrative.yourdomain.com
- `BACKEND_CORS_ORIGINS`: https://narrative.yourdomain.com (explicit origin(s); the backend refuses `*` in production-like envs)
- `ALLOWED_ORIGINS`: https://narrative.yourdomain.com (frontend page-middleware CORS allowlist)
- Google/GitHub OAuth credentials (if using authentication)

**Save and secure the file**:
```bash
chmod 600 .env.staging
```

---

## Step 5: Deploy Application Code

### Option A: Manual Deployment (First Time)

```bash
# SSH as narrative-deploy user
ssh narrative-deploy@47.88.89.175
cd /opt/narrative-modeling-app/staging

# Clone repository
git clone https://github.com/frankbria/narrative-modeling-app.git .

# Checkout main branch
git checkout main

# Build and start services (--env-file is required: compose only auto-reads
# a file literally named .env, and secrets live in .env.staging)
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build

# Check status
docker compose -f docker-compose.staging.yml --env-file .env.staging ps

# View logs
docker compose -f docker-compose.staging.yml --env-file .env.staging logs -f
```

### Option B: Automated Deployment (via GitHub Actions)

Implemented in `.github/workflows/deploy.yml` (issue #150). On every push to
`main` (and via manual `workflow_dispatch`), the workflow SSHes into the staging
server, fast-forwards the deploy checkout to `origin/main`, and rebuilds the
stack with `docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build`, then
polls the backend `/health` endpoint (host port 8010).

**One-time setup** — add these repository secrets
(Settings → Secrets and variables → Actions):

| Secret | Value |
| --- | --- |
| `STAGING_SSH_PRIVATE_KEY` | Private key authorized for the deploy user (see Step 2) |
| `STAGING_HOST` | `dev.briaanalytics.com` (or `47.88.89.175`) |
| `STAGING_USER` | `narrative-deploy` |
| `STAGING_DEPLOY_PATH` | Optional; defaults to `/opt/narrative-modeling-app/staging` |

Until these are set, the deploy job is a **no-op that succeeds with a warning**,
so `main` stays green. Application secrets stay in `.env.staging` **on the
server** and are never passed through CI. The deploy checkout must already exist
at `STAGING_DEPLOY_PATH` with `origin` pointing at this repo (Step 5, Option A).

---

## Step 6: Configure Nginx Reverse Proxy

```bash
# SSH as root
ssh root@47.88.89.175

# Copy nginx configuration
nano /etc/nginx/sites-available/narrative-staging.conf
# Paste contents from nginx-staging.conf
# Replace yourdomain.com with actual domain

# Test nginx configuration
nginx -t

# If test passes, enable the site
ln -s /etc/nginx/sites-available/narrative-staging.conf /etc/nginx/sites-enabled/

# Reload nginx
systemctl reload nginx
```

---

## Step 7: Setup SSL Certificate (Let's Encrypt)

```bash
# Install certbot (if not already installed)
apt-get install certbot python3-certbot-nginx -y

# Obtain SSL certificate
certbot --nginx -d narrative.yourdomain.com

# Certbot will automatically:
# 1. Obtain certificate
# 2. Update nginx configuration
# 3. Set up auto-renewal

# Verify auto-renewal
certbot renew --dry-run
```

---

## Step 8: Configure Firewall (UFW)

```bash
# Check UFW status
ufw status

# No app ports need to be opened: nginx (80/443) proxies to the frontend
# (3011) and backend (8010) on localhost, and Redis (6381) is internal.
# MongoDB is in Atlas — ensure the server's public IP is in the Atlas
# project's IP Access List instead.

# Reload firewall
ufw reload

# Verify rules
ufw status numbered
```

---

## Step 9: Verify Deployment

```bash
# Check all containers are running
docker compose -f docker-compose.staging.yml --env-file .env.staging ps

# Expected output:
# narrative-staging-backend    Up (healthy)
# narrative-staging-frontend   Up (healthy)
# narrative-staging-redis      Up (healthy)

# Test backend health endpoint
curl http://localhost:8010/health
# Expected: {"status": "healthy"}

# Test frontend
curl http://localhost:3011
# Expected: HTML response

# Test via nginx (external access)
curl https://narrative.yourdomain.com/api/health
# Expected: {"status": "healthy"}

# Test frontend via nginx
curl https://narrative.yourdomain.com
# Expected: HTML response
```

---

## Step 10: Smoke Tests

Access the application in browser:

- [ ] Visit `https://narrative.yourdomain.com`
- [ ] Verify homepage loads
- [ ] Test login/authentication
- [ ] Upload a test dataset
- [ ] Verify data appears in database
- [ ] Check backend logs for errors

---

## Monitoring and Maintenance

### View Logs

```bash
# All services
docker compose -f docker-compose.staging.yml --env-file .env.staging logs -f

# Specific service
docker compose -f docker-compose.staging.yml --env-file .env.staging logs -f backend

# Last 100 lines
docker compose -f docker-compose.staging.yml --env-file .env.staging logs --tail=100 backend
```

### Restart Services

```bash
# Restart all
docker compose -f docker-compose.staging.yml --env-file .env.staging restart

# Restart specific service
docker compose -f docker-compose.staging.yml --env-file .env.staging restart backend
```

### Update Application

```bash
# SSH as narrative-deploy
ssh narrative-deploy@47.88.89.175
cd /opt/narrative-modeling-app/staging

# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build

# Verify
docker compose -f docker-compose.staging.yml --env-file .env.staging ps
```

### Database Backup

MongoDB lives in Atlas — use Atlas's built-in backups (Cloud Backup is on by
default for M10+; for free/shared tiers run `mongodump` against the Atlas URI):

```bash
mongodump --uri "$MONGODB_URI" \
  --out /opt/narrative-modeling-app/backups/mongodb-$(date +%Y%m%d-%H%M%S)
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs for errors
docker compose -f docker-compose.staging.yml --env-file .env.staging logs [service-name]

# Check container status
docker compose -f docker-compose.staging.yml --env-file .env.staging ps -a

# Inspect specific container
docker inspect narrative-staging-backend
```

### MongoDB (Atlas) connection issues

```bash
# Test the Atlas connection string from the server
mongosh "$MONGODB_URI" --eval "db.adminCommand('ping')"

# Common causes:
# - Server IP missing from the Atlas project's IP Access List
# - Wrong username/password in MONGODB_URI
# - DNS: mongodb+srv requires working SRV lookups (dig SRV _mongodb._tcp.<cluster-host>)
```

### Nginx issues

```bash
# Test configuration
nginx -t

# Check nginx error log
tail -f /var/log/nginx/narrative-staging-error.log

# Restart nginx
systemctl restart nginx
```

### Network issues

```bash
# Check if services can communicate
docker exec narrative-staging-backend ping redis

# Check Atlas reachability from inside the backend container
docker exec narrative-staging-backend python -c "import os,pymongo; pymongo.MongoClient(os.environ['MONGODB_URI']).admin.command('ping'); print('atlas ok')"
```

---

## Rollback Procedure

If deployment fails:

```bash
# Stop services
docker compose -f docker-compose.staging.yml --env-file .env.staging down

# Checkout previous working commit
git log --oneline -n 10  # Find previous commit
git checkout <previous-commit-hash>

# Rebuild and restart
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build

# Verify
docker compose -f docker-compose.staging.yml --env-file .env.staging ps
```

---

## Security Checklist

Post-deployment security verification:

- [ ] All services running with authentication enabled
- [ ] Atlas IP Access List restricted to the staging server (no 0.0.0.0/0)
- [ ] Redis requires password
- [ ] SSL/TLS certificate installed and valid
- [ ] Firewall rules configured
- [ ] .env.staging file has restricted permissions (600)
- [ ] No secrets in git repository
- [ ] Nginx security headers configured
- [ ] Regular backups scheduled

---

## Next Steps After Staging

1. **Set up automated backups** (daily MongoDB dumps to S3)
2. **Configure monitoring** (Prometheus + Grafana or similar)
3. **Set up log aggregation** (ELK stack or CloudWatch)
4. **Document production deployment** process
5. **Set up staging→production promotion** workflow

---

**Last Updated**: 2025-10-22
**Status**: Ready for first deployment
