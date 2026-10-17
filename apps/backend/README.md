# SheetPredict Backend

FastAPI service behind the SheetPredict frontend: uploads, data preparation, AutoML
training, evaluation and serving.

- Async FastAPI; MongoDB through Beanie (models listed in `app/models/registry.py`)
- S3 for datasets and model artifacts (LocalStack locally)
- OpenAI (JSON mode) behind a circuit breaker, with a rule-based fallback: every
  endpoint works without an API key
- Redis (optional) for caching and rate-limit buckets; without it the limiter uses a
  process-local store
- Auth: an HS256 JWT minted by the frontend's NextAuth session, verified with
  `NEXTAUTH_SECRET`

## Setup

Requires Python 3.13 (`.python-version`) and [uv](https://docs.astral.sh/uv/).

```bash
cd apps/backend
uv sync                 # includes the dev group (pytest, ruff, mypy)
cp .env.example .env    # then edit; .env.example documents each variable
```

Infrastructure (MongoDB + LocalStack) and the `.env` values that match it:
[docs/dev/LOCAL_DEVELOPMENT.md](../../docs/dev/LOCAL_DEVELOPMENT.md). Required:
`MONGODB_URI` (bare) + `MONGODB_DB`, the S3 settings, `NEXTAUTH_SECRET`, `ENVIRONMENT`.

## Run

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- `GET /health` (liveness), `GET /health/ready` (MongoDB only; 200 or 503)
- Interactive docs: `/docs`; schema: `/api/v1/openapi.json`
- Published API description: `GET /api/v1/docs/openapi.json` and `.yaml`

The container image runs gunicorn on port 8000 (`Dockerfile`); deployment is in
[docs/ops/STAGING_DEPLOYMENT_GUIDE.md](../../docs/ops/STAGING_DEPLOYMENT_GUIDE.md).

## Authentication

Send the frontend's `session.apiToken` as `Authorization: Bearer <token>`. Production
model endpoints (`/api/v1/production/v1/models/...`) take an `X-API-Key` instead.

`SKIP_AUTH=true` maps every request to `dev-user-default`. The backend refuses to start
with it unless `ENVIRONMENT` is `development` or `test`. Never expose such an instance
beyond `127.0.0.1`.

## API surface

Everything except health, `/metrics` (admin only) and the Stripe webhook
(`/webhooks/stripe/webhook`) is under `/api/v1`. Main groups:

| Prefix | What |
|---|---|
| `/upload` | `/secure`, `/confirm-pii-upload`, chunked upload (`/chunked/...`) |
| `/datasets`, `/user_data` | list, read, preview, schema, process, delete, `/erase` |
| `/transformations` | engine steps, preview/apply, undo/redo history, export code |
| `/ml` | `POST /ml/train`, jobs, evaluation, report, feature importance, SHAP, SDK, `/{id}/predict` |
| `/batch/jobs` | batch prediction jobs |
| `/production/v1/models/{id}/predict` | API-key serving |
| `/ai` | analysis, insights, summaries, chat |
| `/billing` | checkout, portal, status |
| `/users/me/erase` | account data erasure |
| `/admin` | admin allowlist only |

`/api/v1/ml/` is the trained-model surface. `/api/v1/models/` is legacy (train, deploy
and performance answer `410 Gone`). The full list is the live `/docs` page.

## Tests and checks

```bash
PYTHONPATH=. uv run pytest tests/ -m "not integration and not performance" -v   # PR gate; needs MongoDB
PYTHONPATH=. uv run pytest tests/ -m integration -v   # also Redis 6380 + LocalStack 4566:
                                                      #   docker compose -f docker-compose.test.yml up -d
uv run ruff check .
uv run mypy app/
```

Services, markers, fixtures and CI: [docs/dev/TEST_INFRASTRUCTURE.md](../../docs/dev/TEST_INFRASTRUCTURE.md).

## Layout

```
apps/backend/
├── app/
│   ├── main.py          # app, middleware, every include_router
│   ├── config.py        # settings and env resolution
│   ├── api/routes/      # route modules
│   ├── auth/            # token verification, admin guard
│   ├── billing/         # plans, quota enforcement, metering, Stripe
│   ├── middleware/      # rate limit, quota refund, upload cleanup, errors, API version
│   ├── models/          # Beanie documents
│   ├── schemas/         # request/response models
│   ├── services/        # business logic
│   ├── utils/           # S3, OpenAI client, datetime, filenames, ...
│   └── sample_datasets/ # onboarding samples
├── scripts/             # operational scripts (see scripts/README.md)
├── tests/
├── docker-compose.test.yml  # Redis + LocalStack for tests
├── Dockerfile
└── pyproject.toml / uv.lock
```

Conventions (route auth, error bodies, S3 keys, erasure, metering) are in the repo-root
[CLAUDE.md](../../CLAUDE.md).

## License

Apache 2.0. See [LICENSE](../../LICENSE) in the repo root.
