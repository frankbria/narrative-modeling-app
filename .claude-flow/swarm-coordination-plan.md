# Swarm Coordination Plan - Narrative Modeling App

**Version**: 1.0
**Date**: 2025-12-26
**Project**: Narrative Modeling App (Sprint 12+)
**Coordinator**: SwarmLead

---

## Executive Summary

This document defines the swarm coordination strategy for the Narrative Modeling App, enabling multiple AI agents to work collaboratively on complex tasks while maintaining code quality, avoiding context contamination, and ensuring efficient parallel execution.

**Key Principles**:
- **Separation of Concerns**: Each agent type has clear boundaries
- **Hook-Based Communication**: No direct agent-to-agent communication via TaskOutput
- **SwarmLead as Router**: Central coordinator routes tasks and escalates blockers
- **Self-Healing**: Agents auto-resolve issues; escalate only when necessary
- **Quality Gates**: Enforced before PR creation

---

## 1. Agent Role Definitions

### 1.1 Frontend Specialist
**Expertise**: Next.js, React, TypeScript, Tailwind CSS, NextAuth v5

**Responsibilities**:
- UI component development
- Client-side state management
- Routing and navigation
- Authentication flows
- Frontend testing (Jest, Playwright)

**Tools**:
- Jest for unit tests
- Playwright for E2E tests
- TypeScript LSP for type checking
- ESLint for linting

**Boundaries**:
- MUST NOT modify backend code (`apps/backend/`)
- MUST NOT modify MCP server code (`apps/mcp/`)
- MUST read `memory/architecture.json` and `memory/api-contracts.json` before API integration

**Hook Responsibilities**:
- Write: `hooks/progress/<task-id>-frontend.json`
- Write: `hooks/artifacts/<task-id>-frontend.json`
- Read: `memory/architecture.json`, `memory/api-contracts.json`

---

### 1.2 Backend Specialist
**Expertise**: FastAPI, Python, MongoDB, Beanie ODM, AWS S3

**Responsibilities**:
- API endpoint development
- Business logic implementation
- Database operations (MongoDB)
- File storage (S3)
- Background task processing
- Backend testing (pytest)

**Tools**:
- pytest for unit and integration tests
- ruff for linting
- mypy for type checking
- MongoDB client

**Boundaries**:
- MUST NOT modify frontend code (`apps/frontend/`)
- MUST NOT modify MCP server code (`apps/mcp/`)
- MUST update `memory/api-contracts.json` when adding/changing endpoints
- MUST check MongoDB availability before integration tests

**Hook Responsibilities**:
- Write: `hooks/progress/<task-id>-backend.json`
- Write: `hooks/artifacts/<task-id>-backend.json`
- Write: `memory/api-contracts.json` (when endpoints change)
- Read: `memory/architecture.json`, `memory/configuration.json`

---

### 1.3 MCP Specialist
**Expertise**: FastMCP framework, MCP protocol, data processing tools

**Responsibilities**:
- MCP server tool development
- Data processing pipeline implementation
- MCP protocol compliance
- Tool testing (pytest)

**Tools**:
- FastMCP SDK
- pytest for testing
- MCP protocol validator

**Boundaries**:
- ISOLATED to `apps/mcp/` directory
- MUST NOT modify frontend or backend code
- MUST document new tools in `memory/mcp-tools.json`

**Hook Responsibilities**:
- Write: `hooks/progress/<task-id>-mcp.json`
- Write: `hooks/artifacts/<task-id>-mcp.json`
- Write: `memory/mcp-tools.json` (when tools added/changed)
- Read: `memory/architecture.json`

---

### 1.4 Test Engineer
**Expertise**: pytest, Jest, Playwright, test coverage, quality assurance

**Responsibilities**:
- Test coverage verification (>85% requirement)
- E2E test development and execution
- Integration test coordination
- Quality gate enforcement
- Test pattern documentation

**Tools**:
- pytest for backend tests
- Jest for frontend unit tests
- Playwright for E2E tests
- Coverage tools (pytest-cov, Jest coverage)

**Boundaries**:
- CROSS-CUTTING: Can work in any layer
- MUST verify quality gates before signaling completion
- MUST write blocker hooks if tests fail after 3 attempts

**Hook Responsibilities**:
- Write: `hooks/progress/<task-id>-testing.json`
- Write: `hooks/blockers/<task-id>-test-failure.json` (if needed)
- Write: `memory/testing-patterns.json` (new patterns)
- Read: `hooks/artifacts/*.json` (to know what to test)

---

### 1.5 DevOps Specialist
**Expertise**: CI/CD, Docker, AWS, MongoDB, deployment, infrastructure

**Responsibilities**:
- Environment configuration
- Database setup and migrations
- AWS S3 bucket management
- CI/CD pipeline maintenance
- Deployment scripts
- Infrastructure as code

**Tools**:
- GitHub Actions
- Docker / Docker Compose
- MongoDB CLI
- AWS CLI
- Terraform (if needed)

**Boundaries**:
- INFRASTRUCTURE ONLY: Does not implement features
- MUST update `memory/configuration.json` when env vars change
- MUST coordinate with Backend Specialist for database changes

**Hook Responsibilities**:
- Write: `hooks/progress/<task-id>-devops.json`
- Write: `hooks/artifacts/<task-id>-infra.json`
- Write: `memory/configuration.json` (when config changes)
- Read: `memory/dependencies.json`

---

### 1.6 Integration Coordinator
**Expertise**: System architecture, cross-layer coordination, feature integration

**Responsibilities**:
- Orchestrate cross-layer features (frontend + backend)
- Spawn and coordinate specialist agents
- Ensure API contract alignment
- Update architecture documentation
- Resolve cross-boundary conflicts

**Tools**:
- All specialist tools (as needed)
- Architectural analysis tools
- Dependency mapping

**Boundaries**:
- ORCHESTRATOR: Spawns other specialists, doesn't implement directly
- MUST update `memory/architecture.json` when system design changes
- MUST ensure API contracts stay synchronized

**Hook Responsibilities**:
- Write: `hooks/progress/<task-id>-integration.json`
- Write: `memory/architecture.json` (architecture changes)
- Write: `memory/api-contracts.json` (contract updates)
- Read: `hooks/artifacts/*.json` (from spawned agents)

---

## 2. Communication Protocols

### 2.1 Hook Types

#### Progress Hooks (`hooks/progress/<task-id>-<agent-type>.json`)
**Purpose**: Track agent progress without context contamination

**Schema**:
```json
{
  "task_id": "sprint-12-auth-flow",
  "agent_type": "frontend-specialist",
  "status": "in_progress",
  "started_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T10:15:00Z",
  "progress_percentage": 65,
  "current_step": "Implementing login form validation",
  "completed_steps": [
    "Created login component",
    "Added form state management",
    "Integrated NextAuth"
  ],
  "next_steps": [
    "Add error handling",
    "Write E2E tests"
  ]
}
```

**Update Frequency**: Every significant step completion or every 15 minutes

---

#### Artifact Hooks (`hooks/artifacts/<task-id>-<agent-type>.json`)
**Purpose**: Declare completed work for dependent agents

**Schema**:
```json
{
  "task_id": "sprint-12-auth-flow",
  "agent_type": "backend-specialist",
  "artifacts": [
    {
      "type": "api_endpoint",
      "path": "/api/auth/login",
      "method": "POST",
      "tests_passing": true,
      "coverage_percentage": 92,
      "location": "apps/backend/app/routers/auth.py"
    },
    {
      "type": "database_model",
      "model_name": "User",
      "location": "apps/backend/app/models/user.py",
      "indexes": ["email", "created_at"]
    }
  ],
  "dependencies_satisfied": true,
  "ready_for_integration": true,
  "completed_at": "2025-12-26T10:30:00Z"
}
```

**Write Trigger**: Agent completes a discrete unit of work

---

#### Blocker Hooks (`hooks/blockers/<task-id>-<blocker-type>.json`)
**Purpose**: Escalate issues requiring SwarmLead intervention

**Schema**:
```json
{
  "task_id": "sprint-12-dataset-export",
  "agent_type": "test-engineer",
  "blocker_type": "integration_test_failure",
  "severity": "high",
  "description": "Integration tests require MongoDB, but connection failing",
  "error_message": "MongoServerError: Authentication failed",
  "attempted_fixes": [
    "Verified MONGODB_URI environment variable",
    "Checked MongoDB service status",
    "Attempted connection with test credentials"
  ],
  "requires_agent": "devops-specialist",
  "requires_human": false,
  "created_at": "2025-12-26T11:00:00Z"
}
```

**Write Trigger**: Agent fails 3 consecutive times OR encounters architectural issue

---

#### Memory Hooks (`memory/*.json`)
**Purpose**: Shared knowledge base preventing duplicate work

See Section 3 for detailed memory structure.

---

### 2.2 Communication Rules

**CRITICAL CONSTRAINTS**:
1. **No Direct Agent Communication**: Agents NEVER use TaskOutput to read other agents' work
2. **SwarmLead as Hub**: Only SwarmLead reads all hooks
3. **Write-Only for Agents**: Agents write their own hooks, read only memory
4. **Hook Immutability**: Once written, artifact hooks are immutable (append-only)
5. **Atomic Updates**: Progress hooks are atomic file replacements

**Read Permissions**:
| Agent Type | Progress | Artifacts | Blockers | Memory |
|------------|----------|-----------|----------|--------|
| Frontend Specialist | Own | None | None | Architecture, API Contracts |
| Backend Specialist | Own | None | None | Architecture, API Contracts, Configuration |
| MCP Specialist | Own | None | None | Architecture |
| Test Engineer | Own | All Artifacts | None | Testing Patterns |
| DevOps Specialist | Own | None | None | Configuration, Dependencies |
| Integration Coordinator | Own | Spawned Agents | None | All Memory |
| SwarmLead | All | All | All | All Memory |

---

## 3. Memory Structure

### 3.1 Architecture Memory (`memory/architecture.json`)
**Owner**: Integration Coordinator
**Readers**: All agents

**Purpose**: Maintain single source of truth for system design

**Schema**:
```json
{
  "version": "1.2",
  "last_updated": "2025-12-26T10:00:00Z",
  "updated_by": "integration-coordinator",
  "components": {
    "frontend": {
      "framework": "Next.js 14",
      "routing": "App Router",
      "auth": "NextAuth v5",
      "state_management": "React Context + Server Components",
      "styling": "Tailwind CSS"
    },
    "backend": {
      "framework": "FastAPI",
      "database": "MongoDB + Beanie ODM",
      "storage": "AWS S3",
      "async_processing": "FastAPI BackgroundTasks"
    },
    "mcp": {
      "framework": "FastMCP",
      "purpose": "Advanced data processing tools"
    }
  },
  "data_flows": {
    "file_upload": [
      "Frontend: File selection",
      "Backend: /api/datasets/upload",
      "Backend: S3 upload",
      "Backend: MongoDB metadata save",
      "Backend: Background AI analysis",
      "Frontend: Poll for results"
    ],
    "authentication": [
      "Frontend: Login form",
      "NextAuth: Provider verification",
      "Backend: User session validation",
      "Backend: MongoDB user lookup"
    ]
  },
  "boundaries": {
    "frontend_backend": "REST API at /api/*",
    "backend_storage": "S3 client with boto3",
    "backend_database": "Beanie ODM models"
  }
}
```

---

### 3.2 API Contract Memory (`memory/api-contracts.json`)
**Owner**: Backend Specialist (writes), Integration Coordinator (reviews)
**Readers**: Frontend Specialist, Integration Coordinator

**Purpose**: Keep frontend and backend synchronized on API expectations

**Schema**:
```json
{
  "version": "2.5",
  "last_updated": "2025-12-26T10:00:00Z",
  "endpoints": {
    "/api/datasets/upload": {
      "method": "POST",
      "request": {
        "content_type": "multipart/form-data",
        "fields": {
          "file": {
            "type": "File",
            "required": true,
            "max_size_mb": 100
          },
          "name": {
            "type": "string",
            "required": false
          }
        }
      },
      "response": {
        "200": {
          "schema": {
            "id": "string",
            "name": "string",
            "size": "number",
            "uploaded_at": "string (ISO 8601)"
          }
        },
        "400": {
          "error": "Invalid file format"
        },
        "413": {
          "error": "File too large"
        }
      },
      "authentication": "required",
      "implemented_in": "apps/backend/app/routers/datasets.py"
    }
  }
}
```

---

### 3.3 Testing Patterns Memory (`memory/testing-patterns.json`)
**Owner**: Test Engineer
**Readers**: All specialists

**Purpose**: Standardize testing approaches across the codebase

**Schema**:
```json
{
  "version": "1.0",
  "last_updated": "2025-12-26T10:00:00Z",
  "patterns": {
    "backend_unit_tests": {
      "description": "Unit tests that don't require MongoDB",
      "command": "cd apps/backend && uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ -v",
      "coverage_requirement": 85,
      "example": "apps/backend/tests/test_utils/test_validators.py"
    },
    "backend_integration_tests": {
      "description": "Tests requiring MongoDB",
      "setup": "Ensure MongoDB running on localhost:27017",
      "command": "cd apps/backend && uv run pytest tests/test_integration/ -v",
      "cleanup": "Drop test database after run"
    },
    "frontend_unit_tests": {
      "description": "Jest unit tests for components",
      "command": "cd apps/frontend && npm test",
      "coverage_requirement": 80
    },
    "e2e_tests": {
      "description": "Playwright end-to-end tests",
      "command": "cd apps/frontend && npm run test:e2e",
      "requires": ["Frontend running", "Backend running", "MongoDB running"]
    }
  },
  "quality_gates": {
    "pre_commit": [
      "All tests pass (100%)",
      "Coverage >85%",
      "No linting errors (ruff, eslint)",
      "No type errors (mypy, tsc)",
      "No TODO/FIXME/NotImplemented markers"
    ],
    "pre_pr": [
      "All quality_gates.pre_commit checks",
      "E2E tests pass",
      "No security vulnerabilities (OWASP scan)",
      "Documentation updated"
    ]
  }
}
```

---

### 3.4 Configuration Memory (`memory/configuration.json`)
**Owner**: DevOps Specialist
**Readers**: Backend Specialist, MCP Specialist

**Purpose**: Track environment configuration and dependencies

**Schema**:
```json
{
  "version": "1.0",
  "last_updated": "2025-12-26T10:00:00Z",
  "environment_variables": {
    "required": {
      "MONGODB_URI": {
        "description": "MongoDB connection string",
        "example": "mongodb://localhost:27017/narrative_modeling",
        "used_by": ["backend", "mcp"]
      },
      "AWS_ACCESS_KEY_ID": {
        "description": "AWS credentials for S3",
        "used_by": ["backend"]
      },
      "NEXTAUTH_SECRET": {
        "description": "NextAuth session encryption key",
        "used_by": ["frontend"]
      },
      "OPENAI_API_KEY": {
        "description": "OpenAI API for AI analysis",
        "used_by": ["backend", "mcp"]
      }
    },
    "optional": {
      "SKIP_AUTH": {
        "description": "Bypass authentication in development",
        "default": "false",
        "used_by": ["backend"]
      }
    }
  },
  "aws_resources": {
    "s3_bucket": {
      "name": "narrative-modeling-datasets",
      "region": "us-east-1",
      "purpose": "Store uploaded dataset files"
    }
  },
  "mongodb_collections": {
    "users": {
      "indexes": ["email", "created_at"]
    },
    "datasets": {
      "indexes": ["user_id", "created_at", "name"]
    },
    "models": {
      "indexes": ["dataset_id", "created_at"]
    }
  }
}
```

---

### 3.5 Sprint History Memory (`memory/sprint-history.json`)
**Owner**: Integration Coordinator
**Readers**: All agents

**Purpose**: Provide context on completed work and prevent regressions

**Schema**:
```json
{
  "current_sprint": 12,
  "sprints": {
    "11": {
      "status": "completed",
      "completed_at": "2025-12-20",
      "features": [
        "Bulk transformation operations",
        "Recipe export functionality",
        "Enhanced test infrastructure"
      ],
      "test_status": {
        "total": 214,
        "passing": 214,
        "coverage": 89
      },
      "known_issues": [],
      "documentation": "apps/backend/docs/SPRINT_11_COMPLETION.md"
    },
    "12": {
      "status": "in_progress",
      "started_at": "2025-12-21",
      "planned_features": [
        "Advanced model diagnostics",
        "Real-time collaboration",
        "Enhanced visualization tools"
      ],
      "current_progress": "Planning phase"
    }
  }
}
```

---

### 3.6 Dependencies Memory (`memory/dependencies.json`)
**Owner**: DevOps Specialist
**Readers**: All specialists

**Purpose**: Track package versions and compatibility constraints

**Schema**:
```json
{
  "version": "1.0",
  "last_updated": "2025-12-26T10:00:00Z",
  "backend": {
    "package_manager": "uv",
    "python_version": "3.11+",
    "key_dependencies": {
      "fastapi": "^0.104.0",
      "beanie": "^1.23.0",
      "boto3": "^1.29.0",
      "pytest": "^7.4.0"
    }
  },
  "frontend": {
    "package_manager": "npm",
    "node_version": "18.x",
    "key_dependencies": {
      "next": "^14.0.0",
      "react": "^18.2.0",
      "next-auth": "^5.0.0-beta",
      "tailwindcss": "^3.3.0"
    }
  },
  "compatibility_notes": {
    "next-auth": "v5 is beta, breaking changes from v4",
    "beanie": "Requires motor 3.x for MongoDB async operations"
  }
}
```

---

### 3.7 MCP Tools Memory (`memory/mcp-tools.json`)
**Owner**: MCP Specialist
**Readers**: All agents

**Purpose**: Document available MCP server tools

**Schema**:
```json
{
  "version": "1.0",
  "last_updated": "2025-12-26T10:00:00Z",
  "tools": {
    "analyze_dataset": {
      "description": "Perform statistical analysis on uploaded dataset",
      "parameters": {
        "dataset_id": "string",
        "analysis_type": "enum[basic, advanced, full]"
      },
      "returns": {
        "statistics": "object",
        "visualizations": "array"
      }
    }
  },
  "installation": {
    "config_file": "~/.config/claude/claude_desktop_config.json",
    "server_name": "narrative-modeling",
    "command": "uv --directory /path/to/apps/mcp run mcp dev server.py"
  }
}
```

---

## 4. Task Delegation Patterns

### 4.1 Pattern: Single-Layer Task
**Scenario**: Task confined to one architectural layer

**Example**: "Add a loading spinner to the dataset list page"

**SwarmLead Decision Process**:
1. Analyze task: Frontend-only, no API changes
2. Check `memory/architecture.json` for component location
3. Spawn: Frontend Specialist

**Agent Workflow**:
```
Frontend Specialist:
  1. Read memory/architecture.json
  2. Implement loading spinner component
  3. Write hooks/progress/task-123-frontend.json (in_progress)
  4. Add tests (Jest)
  5. Write hooks/artifacts/task-123-frontend.json
  6. Update hooks/progress/task-123-frontend.json (completed)

SwarmLead:
  1. Read hooks/progress/task-123-frontend.json
  2. Spawn Test Engineer for verification

Test Engineer:
  1. Read hooks/artifacts/task-123-frontend.json
  2. Run frontend tests
  3. Verify coverage >85%
  4. Write hooks/progress/task-123-testing.json (completed)
```

**Communication**: Minimal, single specialist

---

### 4.2 Pattern: Cross-Layer Feature
**Scenario**: Task spans multiple architectural layers

**Example**: "Implement dataset export to CSV functionality"

**SwarmLead Decision Process**:
1. Analyze task: Frontend (export button) + Backend (CSV generation)
2. Check `memory/api-contracts.json` for existing export endpoints
3. Spawn: Integration Coordinator

**Agent Workflow**:
```
Integration Coordinator:
  1. Read memory/architecture.json, memory/api-contracts.json
  2. Design API contract: POST /api/datasets/{id}/export
  3. Write memory/api-contracts.json (add new endpoint)
  4. Spawn Backend Specialist (CSV generation)
  5. Spawn Frontend Specialist (export button + download)
  6. Write hooks/progress/task-124-integration.json (coordinating)

Backend Specialist (parallel):
  1. Read memory/api-contracts.json
  2. Implement /api/datasets/{id}/export endpoint
  3. Add CSV conversion logic
  4. Write tests (pytest)
  5. Write hooks/artifacts/task-124-backend.json

Frontend Specialist (parallel):
  1. Read memory/api-contracts.json
  2. Add export button to UI
  3. Implement file download logic
  4. Write tests (Jest)
  5. Write hooks/artifacts/task-124-frontend.json

Integration Coordinator:
  1. Read hooks/artifacts/task-124-backend.json
  2. Read hooks/artifacts/task-124-frontend.json
  3. Verify API contract alignment
  4. Write hooks/progress/task-124-integration.json (completed)

SwarmLead:
  1. Spawn Test Engineer for E2E verification

Test Engineer:
  1. Run E2E test: Click export → Download CSV → Verify content
  2. Write hooks/progress/task-124-testing.json (completed)
```

**Communication**: Integration Coordinator reads artifact hooks to coordinate

---

### 4.3 Pattern: Quality Gate Verification
**Scenario**: Task requires comprehensive testing before PR

**Example**: "Verify Sprint 12 features ready for deployment"

**SwarmLead Decision Process**:
1. Analyze task: Quality assurance, no new code
2. Spawn: Test Engineer

**Agent Workflow**:
```
Test Engineer:
  1. Read memory/testing-patterns.json
  2. Run all backend tests: 214/214 passing
  3. Run all frontend tests: Jest + Playwright
  4. Check coverage: >85% ✓
  5. Run linting: ruff (backend), eslint (frontend)
  6. Run type checking: mypy (backend), tsc (frontend)
  7. Scan for markers: TODO/FIXME/NotImplemented
  8. Run security scan: OWASP patterns
  9. Write hooks/progress/task-125-testing.json

  If all pass:
    hooks/progress/task-125-testing.json → status: completed

  If any fail:
    hooks/blockers/task-125-test-failure.json → details + error logs

SwarmLead:
  If blocker exists:
    1. Read blocker hook
    2. Analyze failure type
    3. Spawn appropriate specialist to fix
```

**Communication**: Test Engineer writes blocker hooks if failures persist

---

### 4.4 Pattern: Infrastructure Change
**Scenario**: Task involves environment, deployment, or configuration

**Example**: "Add Redis caching layer for API responses"

**SwarmLead Decision Process**:
1. Analyze task: Infrastructure (Redis) + Backend (integration)
2. Spawn: DevOps Specialist + Backend Specialist

**Agent Workflow**:
```
DevOps Specialist:
  1. Read memory/configuration.json, memory/dependencies.json
  2. Add Redis to docker-compose.yml
  3. Update .env.example with REDIS_URI
  4. Write deployment script for production Redis
  5. Update memory/configuration.json (add Redis config)
  6. Update memory/dependencies.json (add redis-py)
  7. Write hooks/artifacts/task-126-devops.json

Backend Specialist:
  1. Read hooks/artifacts/task-126-devops.json (wait for Redis ready)
  2. Read memory/configuration.json (get Redis config)
  3. Implement Redis client in app/utils/cache.py
  4. Add caching decorators to API routes
  5. Write tests with Redis mock
  6. Write hooks/artifacts/task-126-backend.json

SwarmLead:
  1. Spawn Test Engineer for integration verification

Test Engineer:
  1. Start Redis locally
  2. Run integration tests with real Redis
  3. Verify cache hit/miss behavior
  4. Write hooks/progress/task-126-testing.json
```

**Communication**: Backend Specialist waits for DevOps artifact hook

---

### 4.5 Pattern: Research/Exploration
**Scenario**: Task requires codebase understanding or documentation lookup

**Example**: "Find all authentication touchpoints in the codebase"

**SwarmLead Decision Process**:
1. Analyze task: Codebase exploration, no code changes
2. Spawn: Exploration Agent (general-purpose with morph-mcp)

**Agent Workflow**:
```
Exploration Agent:
  1. Use morph-mcp.warpgrep_codebase_search:
     query: "authentication logic"
  2. Analyze results: NextAuth, backend validators, session checks
  3. Map authentication flow
  4. Write memory/authentication-touchpoints.json
  5. Write hooks/progress/task-127-exploration.json (completed)

SwarmLead:
  1. Read memory/authentication-touchpoints.json
  2. Share findings with user (no further action needed)
```

**Communication**: Writes findings to memory for future reference

---

### 4.6 Pattern: Bug Investigation
**Scenario**: Task requires debugging across layers

**Example**: "Fix: Authentication redirect loop on production"

**SwarmLead Decision Process**:
1. Analyze task: Cross-layer debugging
2. Spawn: Integration Coordinator (with debugging focus)

**Agent Workflow**:
```
Integration Coordinator:
  1. Read memory/architecture.json (understand auth flow)
  2. Use morph-mcp.warpgrep_codebase_search: "redirect authentication"
  3. Analyze logs (if available)
  4. Identify hypothesis: NEXTAUTH_URL mismatch in production
  5. Write memory/bug-investigation-task-128.json
  6. Spawn Frontend Specialist to verify NextAuth config
  7. Spawn DevOps Specialist to check production env vars

Frontend Specialist:
  1. Check apps/frontend/app/api/auth/[...nextauth]/route.ts
  2. Verify NEXTAUTH_URL usage
  3. Write hooks/artifacts/task-128-frontend.json (findings)

DevOps Specialist:
  1. Check production .env file
  2. Find: NEXTAUTH_URL=http://localhost:3000 (WRONG)
  3. Fix: NEXTAUTH_URL=https://app.narrativemodeling.com
  4. Write hooks/artifacts/task-128-devops.json (fix applied)

Integration Coordinator:
  1. Read artifact hooks from both specialists
  2. Confirm fix resolves issue
  3. Write hooks/progress/task-128-integration.json (completed)

SwarmLead:
  1. Spawn Test Engineer to verify fix in production
```

**Communication**: Integration Coordinator orchestrates via artifact hooks

---

## 5. Swarm Topology

### 5.1 Hierarchy Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         SwarmLead                               │
│                    (Central Coordinator)                        │
│                                                                 │
│  Responsibilities:                                              │
│  • Task analysis and routing                                   │
│  • Read ALL hooks (progress, artifacts, blockers, memory)      │
│  • Escalate blockers                                            │
│  • Enforce quality gates                                        │
│  • Spawn appropriate agents                                     │
└───────────────────────┬─────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────────┐ ┌──────────────┐ ┌──────────────┐
│   Frontend    │ │   Backend    │ │     MCP      │
│  Specialist   │ │  Specialist  │ │  Specialist  │
├───────────────┤ ├──────────────┤ ├──────────────┤
│ Next.js, TS   │ │ FastAPI, Py  │ │  FastMCP     │
│ Tailwind      │ │ MongoDB, S3  │ │  Tools       │
│ NextAuth      │ │ Beanie ODM   │ │  Processing  │
├───────────────┤ ├──────────────┤ ├──────────────┤
│ Writes:       │ │ Writes:      │ │ Writes:      │
│ • Progress    │ │ • Progress   │ │ • Progress   │
│ • Artifacts   │ │ • Artifacts  │ │ • Artifacts  │
│               │ │ • API Ctrcts │ │ • MCP Tools  │
│ Reads:        │ │ Reads:       │ │ Reads:       │
│ • Arch        │ │ • Arch       │ │ • Arch       │
│ • API Ctrcts  │ │ • API Ctrcts │ │              │
│               │ │ • Config     │ │              │
└───────┬───────┘ └──────┬───────┘ └──────┬───────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
                ┌────────────────┐
                │      Test      │
                │    Engineer    │
                ├────────────────┤
                │ pytest, Jest   │
                │ Playwright     │
                │ Coverage       │
                ├────────────────┤
                │ Writes:        │
                │ • Progress     │
                │ • Blockers     │
                │ • Test Ptrns   │
                │ Reads:         │
                │ • Artifacts    │
                │ • Test Ptrns   │
                └────────┬───────┘
                         │
                ┌────────┴────────┐
                │                 │
                ▼                 ▼
        ┌───────────────┐ ┌──────────────┐
        │   DevOps      │ │ Integration  │
        │  Specialist   │ │ Coordinator  │
        ├───────────────┤ ├──────────────┤
        │ CI/CD, Docker │ │ Orchestrator │
        │ AWS, MongoDB  │ │ Cross-layer  │
        │ Infra         │ │ Features     │
        ├───────────────┤ ├──────────────┤
        │ Writes:       │ │ Writes:      │
        │ • Progress    │ │ • Progress   │
        │ • Infra Arts  │ │ • Arch       │
        │ • Config      │ │ • API Ctrcts │
        │ Reads:        │ │ Reads:       │
        │ • Config      │ │ • All Arts   │
        │ • Deps        │ │ • All Memory │
        └───────────────┘ └──────────────┘
```

### 5.2 Coordination Flow

**Sequential Tasks**:
```
User Request → SwarmLead Analysis → Spawn Specialist →
  Specialist Completes → Writes Artifact Hook →
    SwarmLead Spawns Test Engineer → Tests Pass →
      SwarmLead Marks Complete
```

**Parallel Tasks**:
```
User Request → SwarmLead Analysis → Spawn Integration Coordinator →
  Integration Coordinator Spawns:
    ├─ Frontend Specialist (parallel)
    ├─ Backend Specialist (parallel)
    └─ MCP Specialist (parallel)

  All write artifact hooks concurrently →
  Integration Coordinator reads artifacts →
  Integration Coordinator verifies alignment →
  SwarmLead spawns Test Engineer →
  E2E tests pass →
  SwarmLead marks complete
```

**Blocker Escalation**:
```
Specialist encounters issue →
  Attempt 1: Self-fix
  Attempt 2: Self-fix
  Attempt 3: Self-fix
  Attempt 3 fails → Write blocker hook →
    SwarmLead reads blocker →
    SwarmLead analyzes root cause →
    SwarmLead spawns helper specialist (e.g., DevOps) →
    Helper resolves blocker →
    Original specialist retries →
    Success
```

---

## 6. Quality Gates and Escalation

### 6.1 Auto-Resolved by Agents

Agents should self-resolve these issues without SwarmLead intervention:

1. **Linting Errors**
   - Tool: ruff (backend), eslint (frontend)
   - Action: Auto-fix with `ruff check --fix`, `eslint --fix`
   - Max Attempts: 1 (linting is deterministic)

2. **Type Errors**
   - Tool: mypy (backend), tsc (frontend)
   - Action: Fix with LSP assistance, add type annotations
   - Max Attempts: 3

3. **Simple Test Failures**
   - Definition: Test fails due to implementation bug (not environment)
   - Action: Debug, fix logic, rerun tests
   - Max Attempts: 3

4. **Outdated Documentation**
   - Detection: Code changes invalidate inline comments
   - Action: Update docstrings, comments, README sections
   - Max Attempts: 1

---

### 6.2 SwarmLead Escalation Triggers

SwarmLead intervention required when:

1. **Blocker Hook Written**
   - Agent explicitly requests help via `hooks/blockers/*.json`
   - SwarmLead reads blocker details and spawns helper

2. **3 Failed Iterations**
   - Agent attempts same fix 3 times, still failing
   - Pattern: `hooks/progress/*.json` shows repeated failures
   - SwarmLead analyzes and tries different approach

3. **Cross-Agent Conflict**
   - Detection: Two agents modify same file simultaneously
   - Git shows merge conflict
   - SwarmLead coordinates resolution

4. **Architecture Change Needed**
   - Agent identifies structural issue (e.g., "API needs GraphQL")
   - Writes blocker: `blocker_type: architecture_decision_required`
   - SwarmLead escalates to human or spawns architect

5. **Security Vulnerability**
   - Agent finds OWASP pattern (SQL injection, XSS, etc.)
   - Writes blocker: `blocker_type: security_vulnerability`
   - SwarmLead spawns security specialist

6. **Environment Issue**
   - Example: MongoDB connection failing, AWS credentials invalid
   - Agent writes blocker: `requires_agent: devops-specialist`
   - SwarmLead spawns DevOps Specialist

---

### 6.3 Escalation Actions

When SwarmLead receives a blocker hook:

**Step 1: Analyze Blocker**
```json
{
  "task_id": "sprint-12-feature-x",
  "agent_type": "backend-specialist",
  "blocker_type": "integration_test_failure",
  "severity": "high",
  "description": "MongoDB connection refused",
  "attempted_fixes": ["Verified URI", "Restarted service"],
  "requires_agent": "devops-specialist"
}
```

**Step 2: Check Memory**
- Read `memory/configuration.json` for expected MongoDB setup
- Read `memory/testing-patterns.json` for integration test requirements

**Step 3: Spawn Helper**
```
SwarmLead spawns DevOps Specialist:
  Task: "Resolve MongoDB connection issue for integration tests"
  Context: Blocker hook content
  Expected Outcome: Write fix to hooks/artifacts/fix-mongodb.json
```

**Step 4: Notify Original Agent**
```
SwarmLead updates hooks/blockers/task-id.json:
  "status": "being_resolved",
  "helper_agent": "devops-specialist",
  "expected_resolution": "2025-12-26T11:30:00Z"
```

**Step 5: Verify Resolution**
```
DevOps writes hooks/artifacts/fix-mongodb.json →
SwarmLead notifies Backend Specialist to retry →
Backend Specialist retries integration tests →
Tests pass →
SwarmLead marks blocker resolved
```

---

### 6.4 Quality Gate Checkpoints

Before PR creation, SwarmLead enforces these gates:

#### Gate 1: Code Completion
- [ ] All progress hooks show `status: "completed"`
- [ ] No progress hooks stuck in `in_progress` for >1 hour
- [ ] All planned artifacts have corresponding artifact hooks

#### Gate 2: Testing
- [ ] Test Engineer hook shows 100% pass rate
- [ ] Coverage >85% (backend), >80% (frontend)
- [ ] No failing tests in any layer

#### Gate 3: Quality
- [ ] No linting errors (ruff, eslint)
- [ ] No type errors (mypy, tsc)
- [ ] No TODO/FIXME/NotImplemented markers in new code

#### Gate 4: Security
- [ ] No OWASP patterns detected
- [ ] No hardcoded credentials
- [ ] No SQL injection vulnerabilities

#### Gate 5: Documentation
- [ ] All new endpoints documented in `memory/api-contracts.json`
- [ ] Architecture changes reflected in `memory/architecture.json`
- [ ] New patterns added to `memory/testing-patterns.json`

#### Gate 6: Integration
- [ ] E2E tests pass (Playwright)
- [ ] API contracts aligned (frontend ↔ backend)
- [ ] No merge conflicts

**If all gates pass**: SwarmLead signals PR ready
**If any gate fails**: SwarmLead identifies failing gate and spawns appropriate specialist

---

## 7. Integration with Existing Workflows

### 7.1 Traycer AI Workflow

**Existing Process**:
1. User saves prompt to `prompts/<issue-id>.txt`
2. User runs `./scripts/traycer-workflow.sh <issue-id>`
3. Script invokes claude-flow

**Integration**:
```bash
# scripts/traycer-workflow.sh (enhanced)
ISSUE_ID=$1
PROMPT_FILE="prompts/${ISSUE_ID}.txt"

# Read prompt
PROMPT=$(cat "$PROMPT_FILE")

# Invoke SwarmLead via claude-flow
npx claude-flow@alpha spawn \
  --agent swarm-lead \
  --task "$PROMPT" \
  --context "issue_id=${ISSUE_ID}" \
  --hooks-dir ".claude-flow/hooks" \
  --memory-dir ".claude-flow/memory"

# Monitor progress
npx claude-flow@alpha status --watch
```

**SwarmLead Workflow**:
1. Receive Traycer prompt as task
2. Analyze task type (single-layer, cross-layer, etc.)
3. Check beads status: `bd status <issue-id>`
4. Spawn appropriate agents
5. Monitor hooks for progress
6. On completion: Update beads: `bd close <issue-id>`
7. Signal PR ready

---

### 7.2 CodeRabbit Integration

**Existing Process**:
- CodeRabbit provides code review feedback
- Max 3 iterations for auto-fix
- Blocker queue for architectural issues

**Integration**:
```
CodeRabbit review feedback → SwarmLead analyzes:

If auto-fixable (style, types, simple bugs):
  SwarmLead spawns appropriate specialist
  Specialist applies fix
  Specialist writes artifact hook
  SwarmLead verifies fix

If architectural issue:
  SwarmLead writes blocker hook
  SwarmLead escalates to human review

If iteration 3 still failing:
  SwarmLead writes blocker: "coderabbit_max_iterations_reached"
  SwarmLead requests human intervention
```

---

### 7.3 Beads Issue Tracking

**Existing Process**:
- `.beads` directory exists
- Use `bd quickstart` for workflow
- Track issues with short labels

**Integration**:
```
SwarmLead checks for .beads directory:

If exists:
  SwarmLead runs: bd status
  SwarmLead identifies open issues
  For each spawned agent:
    Agent updates beads: bd update <issue-id> --progress "Implementing X"
  On completion:
    SwarmLead runs: bd close <issue-id>

If not exists:
  SwarmLead runs: bd onboard
  SwarmLead initializes issue tracking
```

**Memory Integration**:
- Beads status reflected in `memory/sprint-history.json`
- SwarmLead syncs beads issues with sprint tracking

---

### 7.4 MCP Tool Precedence

All agents follow these MCP precedence rules:

#### Semantic Code Search
```
❌ NEVER: Grep tool for "find auth logic"
✅ ALWAYS: npx mcporter call morph-mcp.warpgrep_codebase_search \
            --args '{"query": "authentication logic"}'
```

#### Web Search
```
❌ NEVER: Built-in WebSearch
✅ ALWAYS: npx mcporter call tavily.tavily_search \
            --args '{"query": "FastAPI background tasks best practices"}'
```

#### Library Documentation
```
❌ NEVER: Assume Tailwind class names
✅ ALWAYS: npx mcporter call context7.query \
            --args '{"library": "tailwindcss", "query": "responsive grid"}'
```

#### Deep Reasoning
```
✅ USE: mcp__sequential-thinking__sequentialthinking
  For: Complex architectural decisions, multi-step debugging
```

**SwarmLead Enforcement**:
- SwarmLead templates include MCP tool usage
- Specialists receive MCP guidelines in spawn context
- Blocker hooks can flag MCP tool misuse

---

### 7.5 Sprint-Based Development

**Existing Process**:
- Sprint 11 complete (214/214 tests)
- Sprint 12 in progress
- Sprint docs in `apps/backend/docs/SPRINTS.md`

**Integration**:
```
SwarmLead maintains sprint context:

On sprint start:
  SwarmLead reads: apps/backend/docs/SPRINTS.md
  SwarmLead updates: memory/sprint-history.json
  SwarmLead initializes: hooks/progress/sprint-12-*.json

During sprint:
  Agents write progress to sprint-specific hooks
  SwarmLead aggregates progress
  SwarmLead updates sprint status in memory

On sprint completion:
  SwarmLead verifies all sprint tasks completed
  SwarmLead runs quality gates
  SwarmLead generates: apps/backend/docs/SPRINT_12_COMPLETION.md
  SwarmLead updates: memory/sprint-history.json
  SwarmLead archives hooks: .claude-flow/archive/sprint-12/
```

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Week 1)
- [ ] Create hook directory structure
- [ ] Initialize memory files with current project state
- [ ] Document agent spawn templates
- [ ] Test single-layer task pattern (Frontend Specialist)

### Phase 2: Coordination (Week 2)
- [ ] Implement SwarmLead task routing logic
- [ ] Test cross-layer feature pattern (Integration Coordinator)
- [ ] Implement blocker escalation workflow
- [ ] Test quality gate enforcement

### Phase 3: Integration (Week 3)
- [ ] Integrate with Traycer workflow script
- [ ] Integrate with beads issue tracking
- [ ] Integrate with CodeRabbit feedback
- [ ] Test parallel agent execution

### Phase 4: Optimization (Week 4)
- [ ] Add metrics collection (hook read/write latency)
- [ ] Optimize memory file structure
- [ ] Add SwarmLead decision logging
- [ ] Create agent performance dashboard

---

## 9. Monitoring and Metrics

### 9.1 Hook Metrics

Track in `.claude-flow/metrics/hook-metrics.json`:

```json
{
  "date": "2025-12-26",
  "progress_hooks": {
    "total_written": 45,
    "average_update_frequency_minutes": 12,
    "agents": {
      "frontend-specialist": 15,
      "backend-specialist": 18,
      "test-engineer": 12
    }
  },
  "artifact_hooks": {
    "total_written": 23,
    "by_type": {
      "api_endpoint": 8,
      "ui_component": 7,
      "database_model": 4,
      "test_suite": 4
    }
  },
  "blocker_hooks": {
    "total_written": 3,
    "resolved": 3,
    "average_resolution_time_minutes": 18
  }
}
```

### 9.2 Agent Performance

Track in `.claude-flow/metrics/agent-metrics.json`:

```json
{
  "date": "2025-12-26",
  "agents": {
    "frontend-specialist": {
      "tasks_completed": 12,
      "average_completion_time_minutes": 25,
      "blockers_written": 1,
      "self_resolved_issues": 8
    },
    "backend-specialist": {
      "tasks_completed": 15,
      "average_completion_time_minutes": 30,
      "blockers_written": 2,
      "self_resolved_issues": 12
    }
  }
}
```

### 9.3 Quality Metrics

Track in `.claude-flow/metrics/quality-metrics.json`:

```json
{
  "date": "2025-12-26",
  "tests": {
    "backend_total": 214,
    "backend_passing": 214,
    "backend_coverage": 89,
    "frontend_total": 87,
    "frontend_passing": 87,
    "frontend_coverage": 82
  },
  "quality_gates": {
    "total_checks": 15,
    "passed_first_attempt": 12,
    "passed_after_fix": 3,
    "failed": 0
  }
}
```

---

## 10. Troubleshooting

### Common Issues

#### Issue: Agent writes blocker hook repeatedly
**Symptom**: Same blocker appears multiple times
**Cause**: SwarmLead not reading blocker hooks
**Fix**: Check SwarmLead hook polling frequency

#### Issue: Artifact hooks not found by dependent agents
**Symptom**: Integration Coordinator can't find backend artifact
**Cause**: File naming mismatch
**Fix**: Enforce strict naming: `hooks/artifacts/<task-id>-<agent-type>.json`

#### Issue: Memory files outdated
**Symptom**: Agents use stale API contracts
**Cause**: Backend Specialist not updating memory
**Fix**: Add memory update verification to quality gates

#### Issue: Too many parallel agents
**Symptom**: Context limits exceeded
**Cause**: SwarmLead spawns too many agents simultaneously
**Fix**: Implement agent pooling (max 5 concurrent agents)

---

## Appendices

### Appendix A: Hook File Naming Conventions

```
hooks/progress/<task-id>-<agent-type>.json
  Example: hooks/progress/sprint-12-auth-frontend.json

hooks/artifacts/<task-id>-<agent-type>.json
  Example: hooks/artifacts/sprint-12-auth-backend.json

hooks/blockers/<task-id>-<blocker-type>.json
  Example: hooks/blockers/sprint-12-auth-test-failure.json

memory/<domain>.json
  Example: memory/api-contracts.json
```

### Appendix B: Agent Spawn Templates

**Frontend Specialist Template**:
```json
{
  "agent_type": "frontend-specialist",
  "task_id": "sprint-12-feature-x",
  "task_description": "Implement login form with validation",
  "context": {
    "read_memory": ["architecture", "api-contracts"],
    "write_hooks": ["progress", "artifacts"],
    "boundaries": ["No backend modifications"],
    "mcp_tools": ["context7 for Tailwind docs"]
  }
}
```

**Backend Specialist Template**:
```json
{
  "agent_type": "backend-specialist",
  "task_id": "sprint-12-feature-x",
  "task_description": "Create /api/auth/login endpoint",
  "context": {
    "read_memory": ["architecture", "api-contracts", "configuration"],
    "write_hooks": ["progress", "artifacts"],
    "update_memory": ["api-contracts"],
    "boundaries": ["No frontend modifications"],
    "mcp_tools": ["context7 for FastAPI docs"]
  }
}
```

---

## Conclusion

This swarm coordination plan establishes a robust framework for multi-agent collaboration on the Narrative Modeling App. By enforcing clear agent boundaries, hook-based communication, and quality gates, we enable:

- **Parallel Execution**: Multiple agents work simultaneously without conflicts
- **Context Efficiency**: Hooks prevent context contamination via TaskOutput
- **Quality Assurance**: Test Engineer and quality gates ensure >85% coverage
- **Self-Healing**: Agents auto-resolve issues, escalate only when needed
- **Integration**: Seamless integration with Traycer, CodeRabbit, and beads workflows

**Next Steps**:
1. Initialize memory files with current project state
2. Test single-layer pattern with Frontend Specialist
3. Iterate on hook schemas based on real usage
4. Expand to cross-layer patterns

**Maintainer**: SwarmLead Coordinator
**Review Cycle**: After each sprint completion
**Version History**: Track in `.claude-flow/docs/COORDINATION_PLAN_CHANGELOG.md`
