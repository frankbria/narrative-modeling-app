# Local Development

Run SheetPredict on one machine: MongoDB and LocalStack S3 in Docker, the backend and
frontend directly.

## Prerequisites

- Docker
- Python 3.13 (`apps/backend/.python-version`) and [uv](https://docs.astral.sh/uv/)
- Node.js `^22.13.0 || >=24` (`apps/frontend/package.json` `engines`; CI uses 22) and npm
- An OpenAI API key is optional: AI endpoints fall back to rule-based output without one.

## 1. Start MongoDB and LocalStack

```bash
./scripts/local-setup.sh
```

Starts two containers bound to `127.0.0.1` and waits until both answer:

- `narrative-mongodb` — `mongo:7` on `27017`, root user `admin` / `localpassword`
- `narrative-localstack` — LocalStack S3 on `4566`, with bucket `narrative-modeling-local`

It is idempotent: a second run reuses the containers.

## 2. Configure the backend

```bash
cd apps/backend
cp .env.example .env
uv sync
```

`.env.example` already names the bucket `scripts/local-setup.sh` creates, but assumes an
unauthenticated Mongo. For the container above, change these lines in `.env`:

```env
MONGODB_URI=mongodb://admin:localpassword@localhost:27017/?authSource=admin
MONGODB_DB=narrative-modeling
TEST_MONGODB_URI=mongodb://admin:localpassword@localhost:27017/?authSource=admin
```

Rules the backend enforces:

- `MONGODB_URI` stays bare; the database is `MONGODB_DB`. If the URI path names a
  database it must equal `MONGODB_DB`, or startup fails.
- `AWS_ENDPOINT_URL=http://localhost:4566` is what keeps local runs on LocalStack.
  LocalStack accepts any credentials, but they must not start with `test-` (that means
  "no storage" to the backend). Never point a local run at a deployed bucket.
- `SKIP_AUTH=true` (the example's value) maps every request to `dev-user-default` and is
  accepted only when `ENVIRONMENT` is `development` or `test`. A `SKIP_AUTH` backend has
  no authentication: bind it to `127.0.0.1` only.

## 3. Configure the frontend

```bash
cd apps/frontend
cp .env.local.example .env.local
npm install
```

In `.env.local`, set:

```env
MONGODB_URI=mongodb://admin:localpassword@localhost:27017/?authSource=admin
MONGODB_DB=narrative-modeling          # same value as the backend
NEXTAUTH_SECRET=<same value as the backend's NEXTAUTH_SECRET>
NEXTAUTH_URL=http://localhost:3000
```

`NEXT_PUBLIC_API_URL` includes `/api/v1` (`http://localhost:8000/api/v1`). Generate a
secret with `openssl rand -base64 32`.

## 4. Run

```bash
# Terminal 1
cd apps/backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2
cd apps/frontend && npm run dev
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (liveness `/health`, readiness `/health/ready`)
- API docs: http://localhost:8000/docs

## Signing in

`next dev` runs with `NODE_ENV=development`, which enables a credentials provider: sign
in as `test@narrativeml.com` / `test-password-123` (override with `TEST_USER_EMAIL` /
`TEST_USER_PASSWORD`). Google and GitHub sign-in need real OAuth apps
(`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`, `GITHUB_ID`/`GITHUB_SECRET`) with callback
URLs `http://localhost:3000/api/auth/callback/google` and `.../github`.

With `SKIP_AUTH=true` the backend ignores who signed in. To exercise real per-user auth
locally, set `SKIP_AUTH=false` in the backend `.env`; the backend then verifies the token
the frontend mints with the shared `NEXTAUTH_SECRET`.

Signup mode: with `SIGNUP_MODE` and `INVITE_ALLOWLIST` unset, development is open. Setting
`INVITE_ALLOWLIST` (or `SIGNUP_MODE=invite`) switches to invite mode, where the
credentials login is refused.

## Tests

```bash
cd apps/backend  && PYTHONPATH=. uv run pytest tests/ -m "not integration and not performance"
cd apps/frontend && npm test && npm run type-check && npm run lint
cd apps/mcp      && uv run pytest tests/
```

Details: [TEST_INFRASTRUCTURE.md](TEST_INFRASTRUCTURE.md),
[E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md). The e2e runner uses port 3010 for the
frontend and 8000 for the backend, and frees both first.

## Inspecting data

```bash
docker exec -it narrative-mongodb mongosh -u admin -p localpassword
#   use narrative-modeling
#   db.user_data.find()

docker exec narrative-localstack awslocal s3 ls s3://narrative-modeling-local/ --recursive
```

## Troubleshooting

- **Port in use:** `lsof -i :3000` (or `:8000`, `:27017`, `:4566`). The test LocalStack
  from `apps/backend/docker-compose.test.yml` also binds 4566; run one or the other.
- **Mongo auth errors:** the URI lacks `admin:localpassword@...?authSource=admin`.
  `local-setup.sh` reuses an existing container with its original credentials.
- **Start over** (deletes local data):
  ```bash
  docker rm -f narrative-mongodb narrative-localstack && ./scripts/local-setup.sh
  ```

Deployment: [../ops/STAGING_DEPLOYMENT_GUIDE.md](../ops/STAGING_DEPLOYMENT_GUIDE.md).
