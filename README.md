# SheetPredict

SheetPredict turns a spreadsheet into a validated, explained, deployable model in minutes — and shows its work.

It is an AI-guided platform for analysts who are not ML engineers: upload a CSV or Excel file, and a guided workflow takes it through profiling, preparation, feature selection, AutoML training, evaluation, prediction and deployment, without writing code.

## What it does

Eight guided stages (`apps/frontend/lib/types/workflow.ts`):

1. **Data loading.** CSV/XLSX upload (100 MB cap, chunked for large files), PII scanning with masking before anything reaches a language model, and sample datasets for onboarding.
2. **Data profiling.** Column statistics, charts, data-quality issues with suggested fixes, and an AI summary.
3. **Data preparation.** A visual pipeline of the four transformations the engine runs (remove duplicates, trim whitespace, drop missing, fill missing), with preview, undo/redo, version history and exportable Python code.
4. **Feature engineering.** Choose features, with identifiers, dates and empty columns detected and excluded automatically.
5. **Model training.** AutoML over several algorithms with optional tuning, bounded per plan tier.
6. **Model evaluation.** Leaderboard against a baseline, metrics, SHAP explanations and a model report that states only what was recorded.
7. **Prediction.** Single-record and batch predictions that warn on unseen or missing inputs.
8. **Deployment.** A REST endpoint secured by API keys and rate limits, drift monitoring, a generated SDK, and self-contained Python/Docker exports.

Every AI feature has a rule-based fallback, so the app works without an OpenAI key. Billing (Stripe) is optional: without keys every account runs on the free tier.

**Not supported yet:** database or cloud-storage connectors, multi-file joins, uploads above 100 MB.

## Repository layout

```
apps/
  backend/    FastAPI API: datasets, transformations, training, serving, billing
  frontend/   Next.js app (App Router, NextAuth v5, Tailwind v4)
  mcp/        MCP server exposing the EDA summary tool to the backend
docs/
  adr/        Architecture decision records (billing, plan limits and pricing)
  dev/        Local development, backend test infrastructure, E2E testing
  ops/        Staging deployment, credential rotation, erasure/backup, artifact integrity
  product/    Positioning and public-surface decisions
scripts/      Local setup, deploy, CI, quality-gate and ops scripts
```

## Tech stack

- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, NextAuth v5 (Google and GitHub sign-in), Jest, Playwright
- **Backend:** Python 3.13, FastAPI, Pydantic, Beanie (MongoDB ODM), pandas, scikit-learn, XGBoost, LightGBM, SHAP, Optuna
- **Data:** MongoDB, Redis (optional: cache and shared rate limiting; without it the limiter is process-local), S3 (LocalStack locally)
- **AI:** OpenAI, behind a circuit breaker, per-tenant quotas and a global daily ceiling
- **Tooling:** uv, npm, Docker, GitHub Actions

## Getting started

Prerequisites: Docker, Python 3.13 with [uv](https://docs.astral.sh/uv/), and Node `^22.13.0 || >=24`.

```bash
# MongoDB on :27017 and LocalStack S3 on :4566, with the dev bucket created
./scripts/local-setup.sh

# Backend on :8000
cd apps/backend
cp .env.example .env          # then apply the Mongo overrides in docs/dev/LOCAL_DEVELOPMENT.md
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend on :3000 (in a second shell)
cd apps/frontend
cp .env.local.example .env.local   # NEXTAUTH_SECRET must equal the backend's
npm install
npm run dev
```

`apps/backend/.env.example` sets `SKIP_AUTH=true`, which maps every request to a single dev user. The backend refuses to start with it unless `ENVIRONMENT` is `development` or `test`. [docs/dev/LOCAL_DEVELOPMENT.md](docs/dev/LOCAL_DEVELOPMENT.md) has the full setup, including real sign-in locally.

## Testing

```bash
# Backend: the PR gate (needs MongoDB on :27017)
cd apps/backend && PYTHONPATH=. uv run pytest tests/ -m "not integration and not performance"

# Frontend
cd apps/frontend && npm test && npm run type-check && npm run lint

# E2E against the real stack
cd apps/frontend && npm run test:e2e:smoke

# MCP server
cd apps/mcp && uv run pytest tests/
```

`.github/workflows/ci.yml` runs all of these on every pull request; `CI Success` is the required check. See [docs/dev/TEST_INFRASTRUCTURE.md](docs/dev/TEST_INFRASTRUCTURE.md) and [docs/dev/E2E_TESTING_GUIDE.md](docs/dev/E2E_TESTING_GUIDE.md).

## Deployment

`main` deploys to staging with `.github/workflows/deploy.yml`, using `docker-compose.staging.yml` behind nginx (`nginx-staging.conf`). The environment templates are `.env.staging.example` and `.env.production.example` at the repo root. Runbooks are in [docs/ops/](docs/ops/), starting with [STAGING_DEPLOYMENT_GUIDE.md](docs/ops/STAGING_DEPLOYMENT_GUIDE.md).

## Contributing

Conventions, architecture rules and the guard tests that enforce them are in [CLAUDE.md](CLAUDE.md). Work on a feature branch and open a pull request against `main`.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE) for attribution.

Copyright © 2025-2026 Noatak Enterprises, LLC, dba Bria Strategy Group

## Author

**Frank Bria** · [frankbria.com](https://frankbria.com) · [@FrankBria18044](https://x.com/FrankBria18044)
