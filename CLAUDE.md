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

### MCP Server
- Located in `apps/mcp/`
- FastMCP framework
- Tools for advanced data processing and modeling

## Code Conventions

### Python (Backend/MCP)
- Use type hints for all function parameters and returns
- Follow PEP 8 style guide
- Use async/await for I/O operations
- Error handling with proper HTTP status codes
- Pydantic models for request/response validation

### TypeScript (Frontend)
- Strict TypeScript mode enabled
- Interfaces over types where appropriate
- Async/await over promises
- Component files use PascalCase
- Utility files use camelCase

### Git Workflow
- Main branch for production
- Feature branches for development
- Descriptive commit messages

## Testing Commands
- Backend: `cd apps/backend && uv run pytest`
- Backend (unit tests only): `cd apps/backend && uv run pytest tests/test_security/ tests/test_processing/ tests/test_utils/ tests/test_model_training/test_problem_detector.py tests/test_model_training/test_feature_engineer.py -v`
- Frontend: `cd apps/frontend && npm test`
- MCP: `cd apps/mcp && uv run pytest`

## Test Suite Status
- Backend: 214/214 tests passing (100%) ✅
  - Unit tests: 203 passing (no database required)
    - Service layer tests: 13 tests (DatasetService)
  - Integration tests: 11 passing (require MongoDB)
- Frontend: Jest tests configured
- MCP: Pytest suite available
- See `apps/backend/docs/TEST_INFRASTRUCTURE.md` for testing guide
- See `apps/backend/docs/TDD_GUIDE.md` for TDD methodology
- See `apps/backend/docs/SPRINT_8_COMPLETION.md` for Sprint 8 details

## Environment Variables
- Frontend: `.env.local`
- Backend: `.env`
- Required: AWS credentials, MongoDB URI, OpenAI API key, NextAuth secret
- Development: Set `SKIP_AUTH=true` to bypass authentication

## Data Flow
1. User uploads file → Backend processes → Stores in S3
2. Metadata saved to MongoDB
3. Background AI analysis triggered
4. Frontend displays results with visualizations

## Current Stage
**Sprint 11 Complete** ✅ - Data model refactoring and performance benchmarking fully implemented. UserData split into focused domain models (DatasetMetadata, TransformationConfig, ModelConfig). Service layer integration completed (Story 11.1B) with DatasetService, TransformationService, and ModelService. Data versioning foundation with lineage tracking. Comprehensive migration testing infrastructure. Performance benchmarks established for all operations. All 37 story points delivered with 100% test pass rate (214 tests passing).

**Sprint 12 Ready** 🟢 - Service layer complete, Sprint 12 unblocked. Ready for API integration, data versioning API, and performance optimization.

Previous Sprints:
- Sprint 10: Monitoring, metrics, and production deployment docs
- Sprint 9: E2E testing infrastructure
- Sprint 8: Resilience patterns, circuit breakers, and API versioning

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

## Feature Development Quality Standards

**CRITICAL**: All new features MUST meet the following mandatory requirements before being considered complete.

### Testing Requirements

- **Minimum Coverage**: 85% code coverage ratio required for all new code
- **Test Pass Rate**: 100% - all tests must pass, no exceptions
- **Test Types Required**:
  - Unit tests for all business logic and services
  - Integration tests for API endpoints
  - End-to-end tests for critical user workflows
- **Coverage Validation**: Run coverage reports before marking features complete:
  ```bash
  # Backend
  cd apps/backend && uv run pytest --cov=app tests/ --cov-report=term-missing
  
  # Frontend
  cd apps/frontend && npm run test:coverage
  
  # MCP
  cd apps/mcp && uv run pytest --cov=app tests/ --cov-report=term-missing
  ```
- **Test Quality**: Tests must validate behavior, not just achieve coverage metrics
- **Test Documentation**: Complex test scenarios must include comments explaining the test strategy

### Git Workflow Requirements

Before moving to the next feature, ALL changes must be:

1. **Committed with Clear Messages**:
   ```bash
   git add .
   git commit -m "feat(module): descriptive message following conventional commits"
   ```
   - Use conventional commit format: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, etc.
   - Include scope when applicable: `feat(backend):`, `fix(frontend):`, `test(mcp):`
   - Write descriptive messages that explain WHAT changed and WHY

2. **Pushed to Remote Repository**:
   ```bash
   git push origin <branch-name>
   ```
   - Never leave completed features uncommitted
   - Push regularly to maintain backup and enable collaboration
   - Ensure CI/CD pipelines pass before considering feature complete

3. **Branch Hygiene**:
   - Work on feature branches, never directly on `main`
   - Branch naming convention: `feature/<feature-name>`, `fix/<issue-name>`, `docs/<doc-update>`
   - Create pull requests for all significant changes

### Documentation Requirements

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

### Feature Completion Checklist

Before marking ANY feature as complete, verify:

- [ ] All tests pass (backend, frontend, MCP)
- [ ] Code coverage meets 85% minimum threshold
- [ ] Coverage report reviewed for meaningful test quality
- [ ] Code formatted and linted (ruff, ESLint)
- [ ] Type checking passes (mypy for Python, tsc for TypeScript)
- [ ] All changes committed with conventional commit messages
- [ ] All commits pushed to remote repository
- [ ] API documentation updated (if applicable)
- [ ] Implementation documentation updated
- [ ] Inline code comments updated or added
- [ ] CLAUDE.md updated (if new patterns introduced)
- [ ] Breaking changes documented
- [ ] CI/CD pipeline passes

### Rationale

These standards ensure:
- **Quality**: High test coverage and pass rates prevent regressions
- **Traceability**: Git commits provide clear history of changes
- **Maintainability**: Current documentation reduces onboarding time and prevents knowledge loss
- **Collaboration**: Pushed changes enable team visibility and code review
- **Reliability**: Consistent quality gates maintain production stability

**Enforcement**: AI agents should automatically apply these standards to all feature development tasks without requiring explicit instruction for each task.
