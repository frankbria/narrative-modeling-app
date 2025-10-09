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
- Backend: 201/201 tests passing (100%) ✅
  - Unit tests: 190 passing (no database required)
  - Integration tests: 11 passing (require MongoDB)
- Frontend: Jest tests configured
- MCP: Pytest suite available
- See `apps/backend/docs/TEST_INFRASTRUCTURE.md` for testing guide
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
**Sprint 8 Complete** ✅ - Resilience patterns and API versioning fully implemented. Circuit breakers protect critical services. Versioned API (v1) with backward compatibility. Test infrastructure overhauled with 100% passing tests. Production-ready with fault tolerance.

Previous: Sprint 7 - JWT authentication, health checks, 8-stage workflow, data transformation pipeline, NextAuth v5.

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