# MongoDB Atlas Migration Status

**Date**: 2025-10-27
**Target**: Staging Environment (dev.briaanalytics.com)
**Current Status**: ⚠️ **PLANNED - NOT IMPLEMENTED**

---

## ⚠️ Important Note

**This migration is PLANNED but NOT YET IMPLEMENTED on the staging server.**

The staging server (dev.briaanalytics.com) currently uses:
- **Self-hosted MongoDB 7.0** running in Docker (container: `narrative-staging-mongodb`)
- Port: 27018
- Status: Healthy, running for 5+ days
- Connection: `mongodb://<USERNAME>:<PASSWORD>@localhost:27018/narrative_staging?authSource=admin`

This document outlines the PLAN for migrating to MongoDB Atlas M0 Free Tier when ready.

---

## 📊 Overall Status

| Component | Status | Notes |
|-----------|--------|-------|
| **Repository Configuration** | ✅ Complete | `.env.staging.example` updated with Atlas format (for future use) |
| **Git History Cleanup** | ✅ Complete | Exposed credentials purged from 275 commits |
| **Documentation** | ⚠️ Revised | Corrected to reflect actual server state (self-hosted) |
| **Server Configuration** | ❌ Not Started | Server still uses self-hosted MongoDB |
| **GitHub Secrets** | ✅ Current | Using self-hosted MongoDB connection string |
| **MongoDB Atlas Setup** | ❌ Not Started | Atlas cluster exists but not actively used |

---

## ✅ Completed Work

### 1. Repository Configuration (Commit 1d464ae)

**Updated Files**:
- `.env.staging.example` - Added MongoDB Atlas connection string format

**Changes**:
```bash
# OLD (self-hosted MongoDB)
MONGODB_ROOT_PASSWORD=<REDACTED>
MONGODB_PASSWORD=<REDACTED>
MONGODB_URI=mongodb://<USERNAME>:<PASSWORD>@localhost:27018/...

# NEW (MongoDB Atlas)
MONGODB_URI=mongodb+srv://<USERNAME>:<PASSWORD>@CLUSTER.mongodb.net/narrative_staging?retryWrites=true&w=majority
MONGODB_DB=narrative_staging
```

**GitHub Secrets Documentation**:
- Fixed naming convention (removed `STAGING_` prefix)
- Documented all required secrets for `staging` environment
- Clarified that GitHub Actions environment scoping handles prefixes automatically

### 2. Git History Cleanup (Commit 154c91e)

**Security Issue**: MongoDB Atlas credentials were exposed in git history

**Exposed Credentials**:
- Password: `<REDACTED — see secret store>`
- Username: `<REDACTED — see secret store>`
- Cluster: `<cluster>.mongodb.net`
- Found in commits: b6935e4 and b779b25
- File: `apps/backend/.env`

**Remediation**:
- Used `git-filter-repo --replace-text` to purge credentials
- Processed 275 commits in 3.42 seconds
- Replaced password with `REDACTED_MONGODB_PASSWORD`
- Force pushed cleaned history to GitHub
- Original HEAD: 4310cfc → New HEAD: 154c91e

**Team Action Required**:
All team members should update their local repositories:
```bash
git fetch origin
git reset --hard origin/main
```

### 3. Documentation Updates

**Updated Files**:
- `docs/deployment/STAGING.md` - Added MongoDB Atlas configuration section
- `.env.staging.example` - Template with Atlas connection string
- `STAGING_MIGRATION_GUIDE.md` - Comprehensive server-side migration guide (NEW)

**Key Documentation Added**:
- MongoDB Atlas M0 Free Tier configuration
- Connection string format and requirements
- IP whitelist requirements
- Database user roles and permissions
- Backup strategy for Atlas
- Troubleshooting section

---

## ⏳ Pending Work

### 1. MongoDB Atlas Credential Rotation (CRITICAL)

**Why**: The exposed password `[REDACTED]` was in git history for an unknown period and must be considered compromised.

**Action Required**:
1. Log in to MongoDB Atlas: https://cloud.mongodb.com
2. Navigate to Database Access for cluster `<cluster>.mongodb.net`
3. Either:
   - Delete user `frankbria` and create new user with different username
   - OR change password for `frankbria` to a new secure password
4. Generate new strong password: `openssl rand -base64 32`
5. Update connection string with new credentials

### 2. Staging Server Configuration

**Status**: Cannot access via SSH from current location

**Required Actions** (Manual - requires server access):
1. SSH to staging server: `ssh narrative-deploy@dev.briaanalytics.com`
2. Update `/opt/narrative-modeling-app/staging/.env.staging` with new MongoDB Atlas credentials
3. Remove old MongoDB variables (`MONGODB_ROOT_PASSWORD`, `MONGODB_PASSWORD`)
4. Stop self-hosted MongoDB container
5. Restart backend service: `sudo systemctl restart narrative-backend`
6. Verify connection and health

**Detailed Instructions**: See `STAGING_MIGRATION_GUIDE.md`

### 3. GitHub Secrets Update

**Repository**: https://github.com/frankbria/narrative-modeling-app/settings/environments

**Environment**: `staging`

**Secret to Update**:
- `MONGODB_URI` - Update with NEW MongoDB Atlas connection string containing rotated password

**Format**:
```
mongodb+srv://<USERNAME>:<PASSWORD>@<cluster>.mongodb.net/narrative_staging?retryWrites=true&w=majority
```

### 4. Verify Staging Deployment

After server configuration, verify:
- [ ] Backend service starts successfully
- [ ] Backend connects to MongoDB Atlas
- [ ] Health endpoint returns 200: `curl https://dev.briaanalytics.com/api/health`
- [ ] Frontend can communicate with backend
- [ ] Can create/retrieve data through API
- [ ] Redis is still running and accessible

---

## 🔍 Current Server Status

**Server**: dev.briaanalytics.com

**What We Know**:
- User indicated staging is "only partially working"
- SSH access is not available from current location
- Documentation is up-to-date but server configuration is not

**What Needs Verification**:
- Current MongoDB configuration on server
- Whether MongoDB Atlas cluster is already set up
- Status of backend service and logs
- Current Redis configuration

---

## 🚨 Critical Security Actions

### Immediate (Before Server Migration)

1. **Rotate MongoDB Atlas Credentials**
   - Change or delete user with exposed password
   - Generate new secure credentials
   - Document new credentials securely

### During Migration

2. **Update Server Configuration**
   - Replace old MongoDB connection string with Atlas
   - Use NEW rotated credentials
   - Remove self-hosted MongoDB variables

3. **Update GitHub Secrets**
   - Update `MONGODB_URI` in staging environment
   - Use NEW rotated credentials

### After Migration

4. **Verify Security**
   - Confirm old credentials no longer work
   - Test that new credentials work
   - Verify IP whitelist in Atlas is correct
   - Check backend logs for successful connections

---

## 📋 Migration Checklist

### Repository Side (✅ COMPLETE)
- [x] Update `.env.staging.example` with Atlas format
- [x] Remove exposed credentials from git history
- [x] Update deployment documentation
- [x] Create server-side migration guide
- [x] Commit and push all changes
- [x] Verify git history is clean

### MongoDB Atlas (⏳ PENDING)
- [ ] Verify Atlas cluster exists and is accessible
- [ ] Rotate credentials (delete or change password)
- [ ] Whitelist the staging server's public IP (resolve: `dig +short dev.briaanalytics.com`)
- [ ] Verify database `narrative_staging` exists
- [ ] Test connection from local machine

### Staging Server (⏳ PENDING)
- [ ] SSH to staging server
- [ ] Backup current `.env.staging` file
- [ ] Update `.env.staging` with Atlas connection string
- [ ] Remove old MongoDB variables
- [ ] Stop self-hosted MongoDB container
- [ ] Update `docker-compose.simple.yml` (remove MongoDB, keep Redis)
- [ ] Restart Redis: `docker compose -f docker-compose.simple.yml up -d redis`
- [ ] Restart backend: `sudo systemctl restart narrative-backend`
- [ ] Check backend logs: `sudo journalctl -u narrative-backend -n 100`
- [ ] Verify health endpoint works
- [ ] Test frontend functionality

### GitHub (⏳ PENDING)
- [ ] Update `MONGODB_URI` secret in staging environment
- [ ] Verify secret format is correct (SRV connection string)
- [ ] Trigger test deployment if automated pipeline exists

### Verification (⏳ PENDING)
- [ ] Backend service running: `sudo systemctl status narrative-backend`
- [ ] MongoDB Atlas connection successful
- [ ] Redis connection successful
- [ ] Health endpoint returns 200
- [ ] Frontend loads successfully
- [ ] Can create data via API
- [ ] Can retrieve data via API
- [ ] No errors in backend logs

---

## 📚 Reference Documents

- **Server Migration Guide**: `STAGING_MIGRATION_GUIDE.md`
- **Staging Deployment Docs**: `docs/deployment/STAGING.md`
- **Environment Template**: `.env.staging.example`
- **Main Deployment Guide**: `DEPLOYMENT.md`

---

## 🔗 Important Links

- **MongoDB Atlas**: https://cloud.mongodb.com
- **GitHub Repository**: https://github.com/frankbria/narrative-modeling-app
- **GitHub Secrets**: https://github.com/frankbria/narrative-modeling-app/settings/environments
- **Staging Frontend**: https://dev.briaanalytics.com
- **Staging Backend**: https://dev.briaanalytics.com/api
- **Health Endpoint**: https://dev.briaanalytics.com/api/health

---

## 🆘 Troubleshooting

### Cannot SSH to Staging Server

**Possible Causes**:
- Firewall blocking connections
- SSH service not running
- Server is down
- Network connectivity issue

**Solutions**:
- Check server status from hosting provider
- Verify SSH keys are configured
- Try from different network location
- Check server logs if accessible via hosting panel

### MongoDB Atlas Connection Fails

**Possible Causes**:
- IP not whitelisted in Atlas
- Invalid credentials
- Incorrect connection string format
- Network connectivity issue

**Solutions**:
See troubleshooting section in `STAGING_MIGRATION_GUIDE.md`

---

**Document Status**: Current
**Last Updated**: 2025-10-27
**Next Action**: Manual server access required to complete migration
