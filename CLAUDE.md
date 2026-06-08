# CLAUDE.md - Project Conventions and Guidelines

## Project Overview
This is a Narrative Modeling App - an AI-guided platform that democratizes machine learning by helping non-expert analysts build, explore, and deploy models without writing code.

## Key Architecture Components

### Frontend (Next.js)
- Located in `apps/frontend/`
- Uses App Router pattern
- TypeScript with strict typing
- Tailwind CSS for styling
- NextAuth v5 for authentication (Google, GitHub providers)

### Backend (FastAPI)
- Located in `apps/backend/`
- FastAPI with async/await patterns
- MongoDB with Beanie ODM
- AWS S3 for file storage
- Background tasks for AI processing

#### AutoML training (issue #75)
- `POST /api/v1/ml/train` runs real AutoML training in a FastAPI `BackgroundTasks` job and creates a `TrainingJob` (`app/models/training_job.py`, registered in `app/models/registry.py`).
- `GET /api/v1/ml/{model_id}/status` returns live progress, the ranked model comparison, rule-based algorithm recommendations, and a plain-language best-model explanation; failures are recorded on the job (status `failed` + `error`) instead of being silently re-raised.
- The engine (`app/services/model_training/automl_engine.py`) applies basic class-imbalance handling (`class_weight="balanced"` when the majority/minority ratio exceeds 2:1) and accepts a `progress_callback`. Result summaries live in `app/services/model_training/comparison.py`.
- **Out of scope / deferred:** real-time WebSocket progress (#76), job cancellation, time-series (ARIMA/Prophet), SMOTE resampling, Quick/Comprehensive training modes (#101), hyperparameter tuning (#77).

### MCP Server
- Located in `apps/mcp/`
- FastMCP framework
- Tools for advanced data processing and modeling

## Testing Commands
- Backend (full suite): `cd apps/backend && uv run pytest` — requires MongoDB on localhost:27017; optional test Redis (6380) and LocalStack (4566) via `docker compose -f docker-compose.test.yml up -d` (tests skip with a reason when these are absent)
- Backend (service-free tests, no services): `cd apps/backend && PYTHONPATH=. uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ tests/test_models/ tests/test_auth/ tests/test_model_training/test_problem_detector.py tests/test_model_training/test_feature_engineer.py -m "not integration and not performance" -v`
- Frontend (unit tests): `cd apps/frontend && npm test`
- Frontend (type check): `cd apps/frontend && npm run type-check`
- MCP: `cd apps/mcp && uv run pytest tests/` (scope to `tests/`; the vendored `fastmcp/tests/` is the upstream library's own suite)

## Test Suite Status
- Backend: full suite green locally (~1,460 passed, ~39 service-gated/documented skips) ✅ — fixed in issue #160
  - During pytest runs the app lifespan uses the **test** database (never production `MONGODB_URI`)
  - Canonical Beanie model registry: `app/models/registry.py` (shared by app lifespan and `setup_database` fixture)
- CI: `ci.yml` is the primary PR gate (issue #150). It runs backend (ruff **blocking**, mypy **advisory**, service-free pytest), frontend (eslint, `tsc --noEmit`, `next build`, jest), MCP pytest, and backend integration tests (MongoDB **service container** on 27017 + Redis/LocalStack from `docker-compose.test.yml`). A single aggregate `CI Success` status is the required check for branch protection on `main`. The old `unit-tests.yml` was consolidated into `ci.yml`; `integration-tests.yml`/`e2e-tests.yml` remain manual (`workflow_dispatch`). `deploy.yml` deploys `main` to staging over SSH (secret-gated; see workflow header) — service requirements documented in each workflow header
- Frontend: Jest tests configured; TypeScript errors eliminated (#166); `npm run type-check` (`tsc --noEmit`) enforced in CI
- MCP: Pytest suite available
- See `apps/backend/docs/TEST_INFRASTRUCTURE.md` for the testing guide and the **Service Prerequisites** table
- See `apps/backend/docs/TDD_GUIDE.md` for TDD methodology

## Environment Variables
- Frontend: `.env.local`
- Backend: `.env`
- Required: AWS credentials, MongoDB URI, OpenAI API key, NextAuth secret
- Development: Set `SKIP_AUTH=true` to bypass authentication — only honored when `ENVIRONMENT` is explicitly `development`/`test`; backend startup fails hard otherwise (#149)

## Data Flow
1. User uploads file → Backend processes → Stores in S3
2. Metadata saved to MongoDB
3. Background AI analysis triggered
4. Frontend displays results with visualizations

## Current Stage
**Sprint 11 Complete** ✅ | **Sprint 12 Ready** 🟢

See `apps/backend/docs/SPRINTS.md` for detailed sprint history.

## MCP Server Setup
This project includes a custom MCP server for advanced data processing. To use it with Claude Desktop:

```json
{
  "mcpServers": {
    "narrative-modeling": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/narrative-modeling-app/apps/mcp",
        "run",
        "mcp",
        "dev",
        "server.py"
      ]
    }
  }
}
```

Add this to `~/.config/claude/claude_desktop_config.json` and restart Claude Desktop. Replace `/path/to/narrative-modeling-app` with your actual project path.

Additional recommended MCP servers:
- **Context7** - For library documentation lookup
- **Serena** - For project memory and session management

## Documentation Requirements

**ALL implementation documentation MUST remain synchronized with the codebase**:

1. **API Documentation**:
   - Update OpenAPI specifications when endpoints change
   - Document all request/response schemas
   - Include example requests and responses
   - Document error responses and status codes

2. **Code Documentation**:
   - Python: Docstrings for all public functions, classes, and modules
   - TypeScript: JSDoc comments for complex functions and components
   - Update inline comments when implementation changes
   - Remove outdated comments immediately

3. **Implementation Documentation**:
   - Update relevant sections in this CLAUDE.md file
   - Keep architecture diagrams current
   - Update configuration examples when defaults change
   - Document breaking changes prominently

4. **README Updates**:
   - Keep feature lists current
   - Update setup instructions when dependencies change
   - Maintain accurate command examples
   - Update version compatibility information

5. **CLAUDE.md Maintenance**:
   - Add new patterns to relevant sections
   - Update "Current Stage" when workflow changes
   - Keep command examples accurate and tested
   - Document new testing patterns or quality gates

## Automated Workflow Configuration

### Traycer AI Integration

When receiving Traycer AI prompts:
1. Save prompt to: `prompts/<issue-id>.txt`
2. Run: `./scripts/traycer-workflow.sh <issue-id>`
3. Monitor: `npx claude-flow@alpha status --watch`
4. Only intervene if blocker queue triggered

### Quality Gates

Before PR creation:
- ✅ All tests must pass (100% requirement)
- ✅ Test coverage >85%
- ✅ Linting (ruff/eslint) passes
- ✅ Type checking (mypy/tsc) passes
- ✅ No TODO/FIXME/NotImplemented markers
- ✅ Security scan (OWASP patterns)

### CodeRabbit Configuration

Max iterations: 3
Auto-fix categories:
- Code style and formatting
- Type errors
- Simple logic bugs
- Documentation improvements

Blocker queue triggers:
- Iteration 3 still has failing tests
- Architecture change suggestions
- Security vulnerabilities requiring human decision
