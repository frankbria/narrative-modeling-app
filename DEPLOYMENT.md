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

### Stage 3: Staging Server ⚠️ **HIGH PRIORITY SETUP**
- **Environment**: 47.88.89.175 (VPS - public IP)
- **Access**: SSH as root
- **Purpose**: Integration testing and sprint demonstrations
- **Usage**:
  - Integration testing
  - Sprint demonstrations
  - QA testing
  - Pre-production validation
- **Status**: 🚧 **NEEDS SETUP** - See [STAGING_DEPLOYMENT_TODO.md](./STAGING_DEPLOYMENT_TODO.md)
- **Constraints**:
  - Server hosts multiple services
  - Default ports will conflict - custom ports required
  - Port discovery and allocation needed

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

### Immediate (Sprint 12)
1. ⚠️ **HIGH PRIORITY**: Configure staging server (47.88.89.175)
   - See [STAGING_DEPLOYMENT_TODO.md](./STAGING_DEPLOYMENT_TODO.md) for detailed setup guide
   - SSH reconnaissance and port discovery
   - Create deployment configuration
2. ✅ **COMPLETED**: Fix integration tests in GitHub Actions (CI/CD health checks)

### Medium Term (Sprint 13+)
3. Set up automated deployment pipeline to staging
4. Configure staging monitoring and logging
5. Establish smoke test suite for staging deployments

### Long Term
6. Configure production environment
7. Set up production monitoring and alerting
8. Implement blue-green or canary deployment strategy

---

**Last Updated**: 2025-10-21
**Environment**: 4-Stage Deployment Process (Local → Dev → Staging → Production)