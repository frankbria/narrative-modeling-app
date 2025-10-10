# Documentation Index

Quick reference guide to all project documentation with clear purposes and target audiences.

---

## 🚀 Getting Started (Start Here)

### Essential Reading
1. **[README.md](README.md)** - Project overview and quick start
   - **Purpose**: High-level introduction to the Narrative Modeling App
   - **Audience**: Everyone (new developers, stakeholders, users)
   - **When**: First document to read

2. **[LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md)** - Development environment setup
   - **Purpose**: Complete local setup instructions for all components
   - **Audience**: Developers setting up the project locally
   - **When**: After reading README, before coding

3. **[CLAUDE.md](CLAUDE.md)** - AI pair programming conventions
   - **Purpose**: Project-specific guidelines for Claude Code assistant
   - **Audience**: Claude Code, developers using AI assistance
   - **When**: Reference during development

---

## 📋 Product & Requirements

### Product Documentation
4. **[PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)** - Product vision and requirements
   - **Purpose**: Comprehensive product specification and user stories
   - **Audience**: Product managers, developers, stakeholders
   - **When**: Understanding product goals and features

5. **[USER_STORIES.md](USER_STORIES.md)** - Detailed user scenarios
   - **Purpose**: User-centric feature descriptions with acceptance criteria
   - **Audience**: Product owners, QA, developers
   - **When**: Implementing or testing features

---

## 🏃 Sprint Planning & Execution

### Current Sprint
6. **Sprint 10** - Next sprint (Monitoring & Documentation)
   - **Purpose**: Next sprint goals (monitoring, API docs, integration tests)
   - **Audience**: Development team, project managers
   - **When**: Sprint planning for Sprint 10 (Weeks 7-8)
   - **Status**: Planning phase
   - **Note**: No active sprint document yet - see SPRINT_IMPLEMENTATION_PLAN.md

### Implementation Roadmap
7. **[SPRINT_IMPLEMENTATION_PLAN.md](SPRINT_IMPLEMENTATION_PLAN.md)** - 8-sprint roadmap
   - **Purpose**: Comprehensive 16-week implementation plan (Sprints 7-14)
   - **Audience**: Technical leads, project managers, developers
   - **When**: Sprint planning, long-term roadmap review
   - **Scope**: Production readiness → Advanced features → Deployment

---

## 🏗️ Component Documentation

### Backend (FastAPI)
8. **[apps/backend/README.md](apps/backend/README.md)** - Backend API documentation
   - **Purpose**: FastAPI backend setup, API endpoints, testing
   - **Audience**: Backend developers, API consumers
   - **When**: Working with backend code or API

### Frontend (Next.js)
9. **[apps/frontend/README.md](apps/frontend/README.md)** - Frontend application guide
   - **Purpose**: Next.js frontend setup, components, styling
   - **Audience**: Frontend developers, UI/UX designers
   - **When**: Working with frontend code

### MCP Server
10. **[apps/mcp/README.md](apps/mcp/README.md)** - MCP server tools and integration
    - **Purpose**: Advanced data processing and ML tools via MCP protocol
    - **Audience**: ML engineers, developers using Claude Desktop
    - **When**: Using MCP tools or setting up Claude Desktop integration

---

## 🚀 Deployment & Operations

### Production Deployment
11. **[PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)** - Production deployment guide
    - **Purpose**: Docker deployment, infrastructure, monitoring setup
    - **Audience**: DevOps engineers, SREs, deployment teams
    - **When**: Deploying to production environments

12. **[PRODUCTION_API_GUIDE.md](PRODUCTION_API_GUIDE.md)** - Production API usage
    - **Purpose**: API key management, prediction endpoints, monitoring
    - **Audience**: API consumers, ML engineers, integration teams
    - **When**: Using production APIs or integrating services

---

## 📚 Historical Reference

### Archived Documentation
Located in `claudedocs/historical/`:

13. **[SPECIFICATION_REVIEW.md](claudedocs/historical/SPECIFICATION_REVIEW.md)** - Expert panel review (2025-10-07)
    - **Purpose**: Multi-domain architectural analysis and recommendations
    - **Historical context**: Initial system assessment

14. **[WORK_LOG.md](claudedocs/historical/WORK_LOG.md)** - Historical development log
    - **Purpose**: Session-by-session implementation tracking
    - **Historical context**: Sprint 7 development details

15. **[Sprint 8 (claudedocs/historical/sprint-8/)](claudedocs/historical/sprint-8/)** - Completed sprint (2025-10-08)
    - **Purpose**: Resilience & API versioning implementation
    - **Historical context**: Circuit breakers, API v1, test infrastructure fixes
    - **Outcome**: 28/28 points (100%), production-ready resilience

16. **[Sprint 9 (claudedocs/historical/sprint-9/)](claudedocs/historical/sprint-9/)** - Completed sprint (2025-10-08 to 10-09)
    - **Purpose**: E2E testing infrastructure with Playwright
    - **Historical context**: 101 E2E tests, 42 integration tests, CI/CD pipeline
    - **Outcome**: 30/30 points (100%), comprehensive test coverage

---

## 📂 Documentation Structure

```
narrative-modeling-app/
├── README.md                      # Project overview
├── CLAUDE.md                      # AI assistant conventions
├── LOCAL_DEVELOPMENT.md           # Local setup guide
├── DOCUMENTATION_INDEX.md         # This file
│
├── PRODUCT_REQUIREMENTS.md        # Product specification
├── USER_STORIES.md                # User scenarios
│
├── SPRINT_IMPLEMENTATION_PLAN.md  # 8-sprint roadmap (Sprints 7-14)
│
├── PRODUCTION_DEPLOYMENT.md       # Deployment guide
├── PRODUCTION_API_GUIDE.md        # Production API docs
│
├── apps/
│   ├── backend/README.md          # Backend documentation
│   ├── frontend/README.md         # Frontend documentation
│   └── mcp/README.md              # MCP server documentation
│
├── docs/
│   └── testing/
│       └── guide.md               # Comprehensive testing guide
│
└── claudedocs/
    ├── historical/                # Archived documents
    │   ├── SPECIFICATION_REVIEW.md
    │   ├── WORK_LOG.md
    │   ├── sprint-8/              # Sprint 8 archive
    │   │   └── SPRINT_8.md
    │   └── sprint-9/              # Sprint 9 archive
    │       ├── SPRINT_9.md
    │       └── SPRINT_9_STORY_1_IMPLEMENTATION.md
    └── archived_docs/             # Deprecated planning docs
```

---

## 🔄 Documentation Maintenance

### Update Frequency
- **README.md**: When major features change
- **SPRINT_X.md**: Daily during active sprint
- **SPRINT_IMPLEMENTATION_PLAN.md**: Weekly or at sprint boundaries
- **Component READMEs**: When APIs or setup changes
- **DOCUMENTATION_INDEX.md**: When docs are added/removed

### Quality Standards
- ✅ Every document has clear purpose statement
- ✅ Target audience explicitly identified
- ✅ "When to use" guidance provided
- ✅ Documents cross-reference related content
- ✅ No duplicate or conflicting information
- ✅ Historical docs moved to archive (not deleted)

### Document Lifecycle
1. **Active**: Current sprint docs, implementation plans, component READMEs
2. **Reference**: Product requirements, deployment guides, API docs
3. **Historical**: Completed sprint docs, reviews, work logs → move to `claudedocs/historical/`
4. **Deprecated**: Outdated plans, old implementations → move to `claudedocs/archived_docs/`

---

## 🆘 Quick Help

**I want to...**
- **Set up the project locally** → [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md)
- **Understand what we're building** → [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)
- **Plan next sprint** → [SPRINT_IMPLEMENTATION_PLAN.md](SPRINT_IMPLEMENTATION_PLAN.md)
- **Run tests** → [docs/testing/guide.md](docs/testing/guide.md)
- **Deploy to production** → [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)
- **Use the API** → [PRODUCTION_API_GUIDE.md](PRODUCTION_API_GUIDE.md)
- **Set up backend** → [apps/backend/README.md](apps/backend/README.md)
- **Set up frontend** → [apps/frontend/README.md](apps/frontend/README.md)
- **Configure Claude Code** → [CLAUDE.md](CLAUDE.md)

---

**Last Updated**: 2025-10-09
**Maintained By**: Development team
**Version**: 2.1 (Sprint 9 complete, documentation archived)
