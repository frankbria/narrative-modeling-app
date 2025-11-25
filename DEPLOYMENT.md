# Deployment Process - Narrative Modeling App

This project follows a 4-stage deployment process to ensure code quality and stability:

## 🎯 4-Stage Deployment Process

### Stage 1: Local Development
- **Environment**: Local development machine
- **Purpose**: Development and initial testing
- **Location**: `/home/frankbria/projects/narrative-modeling-app`
- **Usage**: Primary development environment where features are built and initially tested

### Stage 2: Dev Server (Internal)
- **Environment**: frankbria-inspiron-7586 (internal network)
- **Purpose**: Development server for team testing
- **Usage**:
  - Team development testing
  - Internal demos
  - Development experimentation
- **Status**: Available for dev team use

### Stage 3: Staging Server ✅ **FULLY DEPLOYED**
- **Environment**: 47.88.89.175 (dev.briaanalytics.com)
- **Access**: SSH as narrative-deploy
- **Purpose**: Integration testing and sprint demonstrations
- **Usage**:
  - Integration testing
  - Sprint demonstrations
  - QA testing
  - Pre-production validation
- **Status**: ✅ **FULLY DEPLOYED** - See [docs/deployment/STAGING.md](./docs/deployment/STAGING.md)
- **Deployed**: October 23, 2025
- **Updated**: October 27, 2025 (Nginx auth routing fixed)
- **Details**:
  - MongoDB 7.0 (self-hosted in Docker, port 27018)
  - Redis 7-alpine (Docker, port 6381)
  - Backend as systemd service (port 8010)
  - Frontend (port 3010)
  - SSL via Let's Encrypt

### Stage 4: Production Deployment
- **Environment**: Live VPS with production configurations
- **Purpose**: End-user production environment
- **Features**:
  - Full production configurations
  - Live user access
  - Production monitoring and logging
  - SSL/TLS enabled
  - Production database backups
- **Status**: Future - will be configured after staging is stable

## Next Steps

### Completed ✅
1. ✅ **DONE**: Staging server fully deployed (47.88.89.175 / dev.briaanalytics.com)
2. ✅ **DONE**: Fix integration tests in GitHub Actions (CI/CD health checks)
3. ✅ **DONE**: E2E test infrastructure optimized (13.8 min vs 20+ min timeouts)

### Current Sprint
4. Fix E2E test failures (7 tests) - See Beads issue narrative-modeling-app-30
5. Set up automated deployment pipeline to staging
6. Configure staging monitoring and logging

### Future
7. Configure production environment
8. Set up production monitoring and alerting
9. Implement blue-green or canary deployment strategy

---

## Documentation

- **Staging Deployment**: [docs/deployment/STAGING.md](./docs/deployment/STAGING.md)
- **Production Planning**: [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)
- **CI Optimization**: [docs/ci/E2E_OPTIMIZATION_2025-10-27.md](./docs/ci/E2E_OPTIMIZATION_2025-10-27.md)

---

**Last Updated**: 2025-10-27
**Environment**: 4-Stage Deployment Process (Local → Dev → Staging → Production)
**Staging Status**: ✅ Fully Operational