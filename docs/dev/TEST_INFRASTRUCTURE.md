# Backend Test Infrastructure

How the backend suite (`apps/backend/tests/`) is selected, which services it needs, and
how CI runs it. Run every command from `apps/backend`. Frontend unit and e2e tests:
[E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md).

## Running tests

```bash
cd apps/backend
uv sync                                                    # installs the dev group too

PYTHONPATH=. uv run pytest tests/ -m "not integration and not performance" -v   # the PR gate
PYTHONPATH=. uv run pytest tests/ -m integration -v        # needs Mongo + Redis + LocalStack
PYTHONPATH=. uv run pytest                                 # everything
uv run ruff check .                                        # lint (CI checks the whole tree)
uv run mypy app/                                           # blocking; must report no issues
```

Selection is by **marker, never by path** (#445). Selecting directories once left most
of the billing, quota, webhook, route and middleware suites outside every required job.

## Markers

Declared in `pytest.ini` (`--strict-markers`, so an undeclared marker fails collection):
`unit`, `integration`, `slow`, `e2e`, `auth`, `security`, `performance`, `load`.

- `integration` — needs a real backing service. Excluded from the PR gate, run by
  `backend-integration`.
- `performance` — wall-clock benchmarks. Everything under `tests/benchmarks/` gets it
  automatically from that directory's `conftest.py`. Excluded from the gate.
- `unit` — `setup_database` skips its Mongo setup for tests carrying it.

## Services

| Service | Endpoint (env var) | Needed by | Start | If absent |
|---|---|---|---|---|
| MongoDB | `localhost:27017` (`TEST_MONGODB_URI`, `TEST_MONGODB_DB`) | route tests, `setup_database`, the app lifespan | local `mongod` or Docker | **required**: DB-backed tests error |
| Redis (test) | `localhost:6380` (`TEST_REDIS_URL`) | `redis_client` fixture | `docker compose -f docker-compose.test.yml up -d redis-test` | skip with reason |
| S3 (LocalStack) | `localhost:4566` (`S3_ENDPOINT_URL`) | `s3_client`, `test_s3_bucket`, `*_localstack.py` | `docker compose -f docker-compose.test.yml up -d localstack` | skip with reason |
| OpenAI | none | — | — | the client is always mocked |

`docker-compose.test.yml` lives in `apps/backend/` and has no MongoDB. The test Redis is
on 6380 so it never touches a dev Redis on 6379.

`TEST_MONGODB_URI` must contain `test` or point at `localhost`/`127.0.0.1`, or
`_point_app_at_test_database` refuses to run. Defaults:
`mongodb://localhost:27017/narrative_modeling_test`, database `narrative_modeling_test`.
If your local Mongo requires auth (e.g. the one `scripts/local-setup.sh` starts), set
`TEST_MONGODB_URI` with credentials in `.env`.

### `CI_REQUIRE_SERVICES`

`tests/conftest.py::require_service()` skips a test whose service is down. With
`CI_REQUIRE_SERVICES=true` it **fails** instead, so CI cannot go green while silently
skipping S3 or Redis (#221). `backend-integration` sets it.

## What `tests/conftest.py` pins

Before any application import:

- `ENVIRONMENT=test` and `RATE_LIMIT_ENABLED=false` (`setdefault`: an exported value
  wins). `ENVIRONMENT` must be `development` or `test` for `SKIP_AUTH` to be accepted.
- S3 settings (#878): `AWS_ENDPOINT_URL` is set to `S3_ENDPOINT_URL` or
  `http://localhost:4566`, and `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_SESSION_TOKEN` are blanked. `app.config` loads `.env` without override, so
  without this a test could reach the bucket your `.env` names. With no credentials
  `S3Service` runs in mock mode and `get_s3_client()` returns `None`, the same as in CI.
  A credential read in a fixture is `os.getenv(NAME) or "test"`, never
  `os.getenv(NAME, "test")` (the variable is set, to nothing).
  `tests/test_services/test_suite_never_reaches_aws.py` holds this.

Session-wide, `_app_uses_the_test_database` points `MONGODB_URI`/`MONGODB_DB` at the test
database, so any test that starts the lifespan uses it. The Beanie model list is
`app/models/registry.py`, shared by the lifespan and `setup_database`.

## Fixtures (`tests/conftest.py`)

| Fixture | Gives |
|---|---|
| `setup_database` | Beanie initialised on the test database; cleaned up after |
| `async_authorized_client` / `authorized_client` | app client with auth overridden — use with real documents |
| `async_test_client` | app client without the auth override |
| `test_user_data`, `test_trained_model`, `test_batch_job` | seeded documents |
| `redis_client`, `test_redis_job` | test Redis (skips if down) |
| `s3_client`, `test_s3_bucket`, `test_s3_file` | LocalStack (skips if down) |
| `mock_openai`, `test_openai_response`, `ai_ceiling_open` | OpenAI stand-ins; `ai_ceiling_open` is needed by any unit test that drives a mocked OpenAI client |
| `beanie_models_initialized` | models on mongomock, for pure model tests |

`tests/api_tokens.py::mint_api_token` mints the HS256 token the backend verifies.
`tests/test_api/conftest.py::mock_async_client` mounts only health and secure upload;
other routes 404 there, so route tests use `async_authorized_client`.

## CI

`.github/workflows/ci.yml` is the PR gate; `CI Success` is the only required check.

- `backend-unit`: `pytest tests/ -m "not integration and not performance" --cov=app`
  against a MongoDB service container. Redis and LocalStack are not provisioned; those
  tests skip here and are enforced below.
- `backend-integration`: `pytest tests/ -m integration --cov=app` with MongoDB and Redis
  (6380) as service containers, LocalStack from `docker-compose.test.yml`, and
  `CI_REQUIRE_SERVICES=true`. It also runs `uv sync --frozen` in `apps/mcp` so the MCP SSE
  round trip runs.
- `backend-lint` (`ruff check .`) and `backend-typecheck` (`mypy app/`).

Together the two test jobs cover the whole tree except the `performance` benchmarks
(`perf-tests.yml`, advisory). `.github/workflows/integration-tests.yml` is a manual run
against an Atlas test cluster.

## Troubleshooting

**Coverage for one file reports nothing (#572).** `--cov` takes a package, dotted module
or directory, not a file path:

```bash
PYTHONPATH=. uv run pytest tests/test_api/test_cache.py --cov=app.api.routes.cache --cov-report=term-missing   # works
PYTHONPATH=. uv run pytest tests/test_api/test_cache.py --cov=app/api/routes/cache.py                          # "No data was collected"
```

**`CircuitBreakerOpen` arrives as `RetryError`.** Tenacity wraps it; assert on
`exc_info.value.__cause__`.

**`ServerSelectionTimeoutError`.** MongoDB is not reachable at `TEST_MONGODB_URI`.

Rules for writing tests (real documents, exact statuses, captured fixtures) are in
[CLAUDE.md](../../CLAUDE.md) under "Test footguns".
