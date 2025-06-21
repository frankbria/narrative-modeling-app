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
- Backend: 132/151 unit tests passing (87.4%)
- Integration tests require MongoDB connection
- See `apps/backend/TEST_STATUS.md` for details

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
Sprint 6+ - Advanced features phase with 8-stage workflow system complete. Data transformation pipeline fully integrated between frontend and backend. NextAuth migration complete. Focus shifting to workflow persistence and advanced ML tools.

## MCP Server Setup
When using Claude Desktop with this project, install the Context7 MCP server for better context management:
```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```
Add this to `~/.config/claude/claude_desktop_config.json` and restart Claude Desktop.