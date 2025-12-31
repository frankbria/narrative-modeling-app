# Claude Flow - Narrative Modeling App Swarm Documentation

**Purpose**: Comprehensive documentation for AI agent swarm orchestration
**Status**: Complete - Ready for swarm activation
**Created**: 2025-12-26

---

## Overview

This directory contains all specifications and guidance for orchestrating a coordinated AI agent swarm for the Narrative Modeling App development. The swarm consists of **3 specialized agents** (TypeScript/React, Python/FastAPI, Python/FastMCP) working in parallel with strong quality gates.

---

## Documents in This Directory

### 1. **project-requirements-analysis.md** (Primary Document)
**Length**: ~740 lines | **Size**: 24 KB
**Audience**: Swarm orchestrators, project managers, technical leads

The comprehensive analysis document covering:
- Project architecture overview (3 apps, 2 languages)
- Common task types and frequency (35-40% frontend, 35-40% backend, 10-15% MCP)
- Quality requirements and gates (100% test pass rate, >85% coverage, security scanning)
- Agent specialization needs (why 3 agents needed, what each does)
- Workflow and coordination patterns
- Project-specific patterns (data versioning, transformation history, security)
- Recent sprint context (Sprint 12 87% complete)
- Tooling and MCP servers
- Success metrics and KPIs

**When to Use**:
- Initial swarm setup and planning
- Understanding project scope
- Defining success criteria
- Making architectural decisions

**Key Sections**:
- Section 2: Common Task Types
- Section 4: Agent Specialization Requirements (detailed)
- Section 5: Workflow & Coordination Patterns
- Section 6: Project-Specific Patterns
- Section 12: Key Resources & Documentation

---

### 2. **AGENT_SPECIFICATIONS.md** (Agent Playbook)
**Length**: ~718 lines | **Size**: 19 KB
**Audience**: Individual agents, agent developers, technical reviewers

Detailed specifications for each agent including:
- **Agent 1: TypeScript/React Expert**
  - Core responsibilities (pages, components, testing, styling)
  - Quality gates (tsc, eslint, jest, coverage >85%)
  - Dependencies and versions
  - Key files and paths
  - Success metrics

- **Agent 2: Python/FastAPI Expert**
  - Core responsibilities (routes, services, schemas, testing)
  - Quality gates (pytest 100%, coverage >85%, mypy, ruff)
  - TDD approach and patterns
  - Integration and performance testing
  - Security implementation
  - Dependencies and versions
  - Success metrics

- **Agent 3: Python/FastMCP Expert**
  - Tool development
  - Integration with backend
  - Testing approach
  - On-demand activation

- **Cross-Agent Coordination**
  - API contract flow
  - Documentation handoff
  - Timing coordination
  - Quality validation

**When to Use**:
- When implementing agent personas
- When validating agent output
- When reviewing code from agents
- When coordinating between agents

**Key Sections**:
- Agent identity, specialization, model recommendations
- Core responsibilities for each agent
- Quality gates (MANDATORY)
- Success metrics
- Common challenges and solutions

---

### 3. **SWARM_QUICK_REFERENCE.md** (Developer Cheatsheet)
**Length**: ~349 lines | **Size**: 9.7 KB
**Audience**: Agents, developers, new team members

Quick reference guide with:
- Swarm composition (3 agents)
- Critical quality requirements (NON-NEGOTIABLE)
- Task distribution matrix
- Key project patterns
- Environment setup commands
- Current sprint status
- Common commands (backend, frontend, MCP)
- Documentation access points
- Coordination protocol
- Troubleshooting quick fixes
- MCP server configuration
- Success criteria and activation checklist

**When to Use**:
- Quick command reference
- During daily development
- When onboarding new agents
- For troubleshooting common issues

**Key Sections**:
- Quality Requirements (copy this to your checklist!)
- Common Commands (bookmark this)
- Documentation Access
- Troubleshooting Quick Fixes

---

## How to Use This Documentation

### For Swarm Orchestrators

1. **Initial Setup**:
   - Read `project-requirements-analysis.md` (Section 1-4)
   - Review `AGENT_SPECIFICATIONS.md` (summary table)
   - Create agent instances with appropriate prompts

2. **Ongoing Management**:
   - Reference `SWARM_QUICK_REFERENCE.md` for common tasks
   - Use quality gates from `AGENT_SPECIFICATIONS.md` for validation
   - Coordinate using patterns in `project-requirements-analysis.md` (Section 5)

3. **Agent Onboarding**:
   - Provide agent with `AGENT_SPECIFICATIONS.md` (relevant section)
   - Share `SWARM_QUICK_REFERENCE.md`
   - Link to key project documentation

### For Individual Agents

1. **Before Starting**:
   - Read your agent section in `AGENT_SPECIFICATIONS.md`
   - Review `SWARM_QUICK_REFERENCE.md` (entire document)
   - Check "Key Files & Paths" in your specification

2. **During Development**:
   - Reference quality gates from `AGENT_SPECIFICATIONS.md`
   - Use commands from `SWARM_QUICK_REFERENCE.md`
   - Follow patterns from `project-requirements-analysis.md` (Section 6)

3. **Before Submission**:
   - Run validation commands from `SWARM_QUICK_REFERENCE.md`
   - Verify all quality gates from `AGENT_SPECIFICATIONS.md`
   - Ensure documentation synchronized

### For Code Reviewers

1. **Validation Checklist**:
   - Copy quality gates from `AGENT_SPECIFICATIONS.md`
   - Use commands from `SWARM_QUICK_REFERENCE.md`
   - Verify documentation updated

2. **Pattern Review**:
   - Check against project patterns (Section 6, project-requirements-analysis.md)
   - Verify cross-agent coordination (Section 5, project-requirements-analysis.md)

---

## Quick Navigation

### By Role

**Swarm Orchestrator** → `project-requirements-analysis.md`
**Frontend Agent** → `AGENT_SPECIFICATIONS.md` (Agent 1 section)
**Backend Agent** → `AGENT_SPECIFICATIONS.md` (Agent 2 section)
**MCP Agent** → `AGENT_SPECIFICATIONS.md` (Agent 3 section)
**Quick Reference** → `SWARM_QUICK_REFERENCE.md`

### By Task

**Setting up swarm** → Sections 4, 9 of project-requirements-analysis.md
**Understanding task types** → Section 2 of project-requirements-analysis.md
**Validating quality** → Quality Gates sections in AGENT_SPECIFICATIONS.md
**Running tests** → SWARM_QUICK_REFERENCE.md (Common Commands)
**Troubleshooting** → SWARM_QUICK_REFERENCE.md (Troubleshooting section)
**Project patterns** → Section 6 of project-requirements-analysis.md

### By Problem

**Agent not writing tests** → AGENT_SPECIFICATIONS.md (Testing sections)
**Type errors in code** → Quality Gates in AGENT_SPECIFICATIONS.md
**API contract mismatch** → Section 5 (API Contract Flow)
**Database tests failing** → SWARM_QUICK_REFERENCE.md (Troubleshooting)
**Performance issues** → Section 6 of project-requirements-analysis.md (Performance)

---

## Key Metrics & Requirements

### Quality Gates (MANDATORY - 100% Required)

```
BACKEND (Python/FastAPI):
✅ pytest: 214/214 tests passing (100%)
✅ Coverage: >85%
✅ mypy: Zero type errors
✅ ruff: Zero linting errors
✅ Security: No cross-tenant leaks, PII detection active
✅ Documentation: API.md + docstrings synchronized

FRONTEND (TypeScript/React):
✅ npm test: All tests passing
✅ npm test:e2e:smoke: All smoke tests passing
✅ Coverage: >85%
✅ tsc --noEmit: Zero type errors
✅ npm run lint: Zero linting errors
✅ Documentation: JSDoc comments + README updated

MCP (Python/FastMCP):
✅ pytest: All tests passing
✅ Tool integration: Tests pass
```

### Performance Targets

| Metric | Target |
|--------|--------|
| P50 (median) | <200ms |
| P95 (95th percentile) | <500ms |
| P99 (99th percentile) | <1s |

### Delivery Targets

| Metric | Target |
|--------|--------|
| Features per Sprint | 3-4 |
| Test Pass Rate | 100% |
| Coverage Target | >85% |
| Documentation Lag | 0 days |
| Bug Fix Time | <2 hours |

---

## Current Project Status

**Sprint 12**: 87% Complete (33/38 story points)

### Completed (4 stories)
- ✅ Story 12.1: API Integration (10 pts)
- ✅ Story 12.2: Data Versioning (8 pts)
- ✅ Story 12.3: Production Deployment (10 pts)
- ✅ Story 12.4: Performance Optimization (5 pts)

### Pending
- 🔵 Story 12.5: E2E Integration Testing (5 pts) - 6-8 hours

### Test Status
- Backend: 214/214 tests passing (100%) ✅
- Frontend: Jest configured, Playwright E2E available
- MCP: Pytest suite available

---

## Swarm Activation Checklist

- [ ] All 3 agents configured and ready
- [ ] MongoDB accessible (docker-compose running)
- [ ] All test suites passing locally
- [ ] Documentation reviewed
- [ ] CodeRabbit configured for reviews
- [ ] GitHub Actions CI/CD working
- [ ] First feature task assigned to swarm
- [ ] Agents understand quality gates
- [ ] Agents know documentation requirements
- [ ] Agents familiar with MCP servers available

---

## Key Files in Project

### Configuration Files
- `CLAUDE.md` - Project conventions and stack preferences
- `pyproject.toml` - Backend dependencies
- `apps/frontend/package.json` - Frontend dependencies
- `apps/mcp/pyproject.toml` - MCP dependencies

### Documentation Files
- `apps/backend/docs/SPRINTS.md` - Sprint history
- `apps/backend/docs/TDD_GUIDE.md` - Testing methodology
- `apps/backend/docs/TEST_INFRASTRUCTURE.md` - Test organization
- `apps/backend/docs/API.md` - API endpoints
- `apps/backend/docs/TRANSFORMATIONS.md` - Transformation patterns
- `apps/backend/docs/VERSIONING.md` - Version system

### Issue Tracking
- `.beads/` - Beads issue database (projects use `bd` commands)
- `.beads/issues.jsonl` - Active issues

---

## Contact & Support

### For Questions About

**Swarm Architecture** → See `project-requirements-analysis.md` (Sections 1-5)
**Agent Capabilities** → See `AGENT_SPECIFICATIONS.md` (Agent sections)
**Daily Development** → See `SWARM_QUICK_REFERENCE.md`
**Testing Patterns** → See `apps/backend/docs/TDD_GUIDE.md`
**API Documentation** → See `apps/backend/docs/API.md`

### Troubleshooting

See **Troubleshooting Quick Fixes** in `SWARM_QUICK_REFERENCE.md`

---

## Document Maintenance

**Last Updated**: 2025-12-26
**Created By**: Requirements Analyst
**Status**: Complete and ready for use
**Next Review**: After first swarm activation cycle

---

## Summary

This documentation provides everything needed to activate and manage a **3-agent swarm** for the Narrative Modeling App:

1. **project-requirements-analysis.md** - Strategic overview and planning
2. **AGENT_SPECIFICATIONS.md** - Tactical implementation guide
3. **SWARM_QUICK_REFERENCE.md** - Operational cheatsheet

Together, these documents define:
- What agents need to do (responsibilities)
- How to validate success (quality gates)
- How to coordinate (workflows)
- What patterns to follow (project-specific)
- How to troubleshoot issues (solutions)

**Start here**: Read `project-requirements-analysis.md` (Executive Summary + Sections 1-4)
**Then**: Assign agents their specifications from `AGENT_SPECIFICATIONS.md`
**Then**: Share `SWARM_QUICK_REFERENCE.md` with all team members

The swarm is ready for activation.
