# Staging Server MongoDB Atlas Migration Guide

**Date**: 2025-10-27
**Server**: 47.88.89.175 (dev.briaanalytics.com)
**Status**: ⚠️ **PLANNED - NOT YET IMPLEMENTED**

---

## ⚠️ Important Note

**This migration guide is for FUTURE USE. The staging server currently uses self-hosted MongoDB 7.0 in Docker.**

Current staging configuration:
- MongoDB 7.0 in Docker (container: `narrative-staging-mongodb`)
- Port: 27018
- Connection: `mongodb://narrative_user:PASSWORD@localhost:27018/narrative_staging?authSource=admin`

This guide documents the PLANNED migration to MongoDB Atlas M0 Free Tier when ready.

---

## ✅ Completed Repository Work

1. **Updated `.env.staging.example`**
   - Added MongoDB Atlas connection string format
   - Removed self-hosted MongoDB credentials
   - Fixed GitHub Secrets naming convention (no `STAGING_` prefix)

2. **Purged Exposed Credentials from Git History**
   - Removed password `ZbKe5a9NGMJ5g91z` from entire git history
   - Processed 275 commits
   - Force pushed cleaned history to GitHub (commit 154c91e)
   - **CRITICAL**: MongoDB Atlas password needs to be rotated immediately

3. **Updated Deployment Documentation**
   - `docs/deployment/STAGING.md` updated with Atlas configuration
   - Connection string format documented
   - IP whitelist requirements documented

---

## 🔧 Required Server-Side Actions

### Step 1: MongoDB Atlas Setup

**If not already done**, create MongoDB Atlas cluster:

1. Log in to https://cloud.mongodb.com
2. Create or use existing M0 Free Tier cluster
3. Create database user with credentials
4. Whitelist staging server IP: `47.88.89.175`
   - Or use `0.0.0.0/0` for staging environment
5. Get connection string (SRV format)

### Step 2: Update Server Environment Configuration

SSH into staging server and update environment file:

```bash
ssh narrative-deploy@47.88.89.175
cd /opt/narrative-modeling-app/staging
```

Edit `.env.staging` and update MongoDB configuration:

```bash
# OLD (self-hosted MongoDB)
# MONGODB_URI=mongodb://narrative_user:PASSWORD@localhost:27018/narrative_staging?authSource=admin
# MONGODB_ROOT_PASSWORD=...
# MONGODB_PASSWORD=...

# NEW (MongoDB Atlas)
MONGODB_URI=mongodb+srv://USERNAME:NEW_PASSWORD@CLUSTER.mongodb.net/narrative_staging?retryWrites=true&w=majority
MONGODB_DB=narrative_staging
```

**Important**:
- Use a **NEW** password (the old one was exposed in git history)
- Replace `USERNAME`, `NEW_PASSWORD`, and `CLUSTER` with actual Atlas credentials
- Remove old `MONGODB_ROOT_PASSWORD` and `MONGODB_PASSWORD` variables

### Step 3: Stop Self-Hosted MongoDB

Stop and remove the self-hosted MongoDB container:

```bash
cd /opt/narrative-modeling-app/staging

# Stop services
docker compose -f docker-compose.simple.yml down

# Edit docker-compose.simple.yml to remove MongoDB service
# (or create a new compose file with only Redis)

# Start only Redis
docker compose -f docker-compose.simple.yml up -d redis
```

### Step 4: Restart Backend Service

Restart the backend to connect to MongoDB Atlas:

```bash
sudo systemctl restart narrative-backend
```

### Step 5: Verify Health

Check that services are healthy:

```bash
# Check backend logs
sudo journalctl -u narrative-backend -n 50

# Test health endpoint
curl https://dev.briaanalytics.com/api/health

# Should return: {"status": "healthy"}
```

### Step 6: Verify MongoDB Connection

Test MongoDB Atlas connection:

```bash
# From staging server
cd /opt/narrative-modeling-app/staging
source .env.staging

# Test with Python
uv run python -c "
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def test():
    client = AsyncIOMotorClient('$MONGODB_URI')
    result = await client.admin.command('ping')
    print('MongoDB Atlas ping successful:', result)
    client.close()

asyncio.run(test())
"
```

### Step 7: Update GitHub Secrets

Update GitHub repository secrets with NEW credentials:

**Navigate to**: https://github.com/frankbria/narrative-modeling-app/settings/environments

**Update in `staging` environment**:
- `MONGODB_URI` - New MongoDB Atlas connection string with new password
- Keep other secrets unchanged:
  - `REDIS_PASSWORD`
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `OPENAI_API_KEY`
  - `BACKEND_SECRET_KEY`
  - `NEXTAUTH_SECRET`
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GITHUB_ID`
  - `GITHUB_SECRET`

---

## 🔍 Troubleshooting

### Backend Won't Start

```bash
# Check service status
sudo systemctl status narrative-backend

# Check logs for errors
sudo journalctl -u narrative-backend -n 100

# Look for MongoDB connection errors
sudo journalctl -u narrative-backend | grep -i mongodb
```

### MongoDB Connection Errors

**Common Issues**:

1. **IP Not Whitelisted**:
   - Go to Atlas → Network Access
   - Add staging server IP: `47.88.89.175`

2. **Invalid Credentials**:
   - Verify username and password in Atlas
   - Check connection string format
   - Ensure password doesn't contain special characters that need URL encoding

3. **Connection String Format**:
   - Must use `mongodb+srv://` for Atlas
   - Must include `?retryWrites=true&w=majority`
   - Database name should be in the path: `/narrative_staging`

### Test Connection Manually

```bash
# Install mongosh if not already installed
sudo apt install -y mongodb-mongosh

# Test connection
mongosh "mongodb+srv://USERNAME:PASSWORD@CLUSTER.mongodb.net/narrative_staging"

# If successful, you should see:
# Current Mongosh Log ID: ...
# Connecting to: mongodb+srv://...
# Using MongoDB: ...
```

---

## 📋 Verification Checklist

After completing migration, verify:

- [ ] MongoDB Atlas cluster is running and accessible
- [ ] Staging server IP is whitelisted in Atlas
- [ ] `.env.staging` file updated with Atlas connection string
- [ ] Old MongoDB container stopped and removed
- [ ] Backend service restarted successfully
- [ ] Backend logs show successful MongoDB connection
- [ ] Health endpoint returns 200 OK
- [ ] GitHub secrets updated with NEW password
- [ ] Old password rotated in Atlas (delete old user or change password)
- [ ] Frontend can communicate with backend
- [ ] Can create/retrieve data through API

---

## 🔐 Security Notes

### Exposed Credentials

The following password was **EXPOSED in git history** and must be rotated:
- **Password**: `ZbKe5a9NGMJ5g91z`
- **Username**: `frankbria`
- **Cluster**: `<cluster>.mongodb.net`

**Action Required**:
1. Log in to MongoDB Atlas
2. Delete user `frankbria` OR change password
3. Create new credentials for staging
4. Update `.env.staging` on server
5. Update GitHub secret `MONGODB_URI`

### Git History Cleaned

- Git history has been rewritten to remove exposed credentials
- All team members should re-clone or run:
  ```bash
  git fetch origin
  git reset --hard origin/main
  ```
- Commit 154c91e is the new HEAD after cleanup

---

## 📝 Reference

### MongoDB Atlas Connection String Format

```bash
mongodb+srv://<username>:<password>@<cluster>.mongodb.net/<database>?retryWrites=true&w=majority
```

**Example**:
```bash
MONGODB_URI=mongodb+srv://staging_user:NewSecurePassword123@cluster0.abc123.mongodb.net/narrative_staging?retryWrites=true&w=majority
```

### Service Management Commands

```bash
# Backend service
sudo systemctl start narrative-backend
sudo systemctl stop narrative-backend
sudo systemctl restart narrative-backend
sudo systemctl status narrative-backend

# Backend logs
sudo journalctl -u narrative-backend -f        # Follow logs
sudo journalctl -u narrative-backend -n 100    # Last 100 lines

# Docker services (Redis only after migration)
docker compose -f docker-compose.simple.yml ps
docker compose -f docker-compose.simple.yml logs -f
docker compose -f docker-compose.simple.yml restart redis
```

---

**Document Status**: Ready for Server-Side Migration
**Created**: 2025-10-27
**Repository Commit**: 154c91e (cleaned history)
