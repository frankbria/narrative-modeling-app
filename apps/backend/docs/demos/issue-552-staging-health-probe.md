# Issue #552: per-subsystem staging probe, on a schedule and after every deploy

*2026-09-16T02:48:15Z*

Staging sat dead behind green signals twice: a rotated Atlas credential (the running process kept its authenticated pool, so only the next restart failed) and a missing S3 bucket (`/health/ready` is Mongo-only by design, #503). `deploy.yml` curled bare `/health`, which is liveness. A local backend is running on :8765 against a scratch Mongo with the developer .env (real S3 + OpenAI keys). First, the old signal — readiness says `ready` no matter what S3 is doing:

```bash
curl -s -w "\nHTTP %{http_code}\n" http://localhost:8765/health/ready
```

```output
{"status":"ready","timestamp":"2026-09-16T02:48:15.852463+00:00","checks":{"mongodb":{"status":"healthy","latency_ms":0.47,"database":"narrative_demo_552"}}}
HTTP 200
```

**AC2 — the probe fails on a dead subsystem that readiness reports around.** Point the S3 resolver at a bucket that does not exist (the staging situation from the issue thread) and run the probe as the workflow does, `python -m app.health_probe`. Every line is a subsystem; the exit code is the verdict:

```bash
cd apps/backend && HEALTH_PROBE_URL=http://localhost:8765 MONGODB_URI=mongodb://localhost:27017 AWS_S3_BUCKET=bucket-that-does-not-exist-552 uv run python -m app.health_probe 2>/dev/null; echo "exit=$?"
```

```output
ready: healthy
mongodb: healthy
mongodb_fresh: healthy
s3: unhealthy
openai: healthy
FAIL: s3
exit=1
```

**AC4 — a stale Mongo credential is caught on a fresh connection while the running service still looks fine.** The service on :8765 keeps its authenticated pool, so its `/health/ready` (and the `mongodb` line copied from it) stays `healthy`. The probe also opens a brand-new connection from `MONGODB_URI` — here pointed at a port where nothing listens, standing in for a rotated password — and that line fails:

```bash
cd apps/backend && HEALTH_PROBE_URL=http://localhost:8765 MONGODB_URI="mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=500" uv run python -m app.health_probe 2>/dev/null; echo "exit=$?"
```

```output
ready: healthy
mongodb: healthy
mongodb_fresh: unreachable (ServerSelectionTimeoutError)
s3: healthy
openai: healthy
FAIL: mongodb_fresh
exit=1
```

With the real bucket and URI back, every subsystem is `healthy` and the probe exits 0 — the only outcome a scheduled run or a deploy gate accepts:

```bash
cd apps/backend && HEALTH_PROBE_URL=http://localhost:8765 MONGODB_URI=mongodb://localhost:27017 uv run python -m app.health_probe 2>/dev/null; echo "exit=$?"
```

```output
ready: healthy
mongodb: healthy
mongodb_fresh: healthy
s3: healthy
openai: healthy
OK: every dependency healthy
exit=0
```

A service that is down at all (worker boot loop after a rotation) is the same verdict, not a crash: `ready` is reported `unreachable` and the fresh-process checks still run.

```bash
actionlint .github/workflows/staging-health.yml .github/workflows/deploy.yml && echo "actionlint: clean"; uv run --project apps/backend python apps/backend/scripts/demo_issue_552.py --workflow
```

```output
actionlint: clean
triggers: {'schedule': [{'cron': '17 * * * *'}], 'workflow_dispatch': None}
permissions: {'contents': 'read', 'issues': 'write'}
step: Check deploy secrets are configured | if: -
step: Connect to Tailscale | if: steps.preflight.outputs.configured == 'true'
step: Configure SSH | if: steps.preflight.outputs.configured == 'true'
step: Run the probe in the backend container | if: steps.preflight.outputs.configured == 'true'
step: Report the failure on an issue | if: failure()
step: Close a recovered alert | if: steps.probe.outcome == 'success'
step: Remove SSH key | if: always()
```

Caveat, stated plainly: the live hourly run needs the Development-environment secrets and a backend image that contains `app/health_probe.py`, which the first post-merge deploy builds. The run itself cannot be witnessed before merge; the wiring is pinned by `test_staging_health_wiring.py` (below) and the first real result lands in the Actions tab after the merge deploy.

**AC3 — the rotation runbook enumerates every consumer.** `docs/operations/CREDENTIAL_ROTATION.md` lists every store (the server env file, the GitHub Environment, the repo secrets, the operator record) and, per secret, which compose services read it. The guard derives the secret list from the real compose file, so a new secret that is not in the table fails the build:

```bash
uv run --project apps/backend python apps/backend/scripts/demo_issue_552.py
```

```output
secret                   backend frontend in-runbook
AWS_ACCESS_KEY_ID        yes     no       yes
AWS_SECRET_ACCESS_KEY    yes     no       yes
BACKEND_SECRET_KEY       yes     no       yes
GITHUB_SECRET            no      yes      yes
GOOGLE_CLIENT_SECRET     no      yes      yes
MONGODB_URI              yes     yes      yes
NEXTAUTH_SECRET          yes     yes      yes
OPENAI_API_KEY           yes     no       yes
REDIS_PASSWORD           yes     yes      yes
SENTRY_DSN               yes     no       yes
STRIPE_SECRET_KEY        yes     no       yes
STRIPE_WEBHOOK_SECRET    yes     no       yes
```

```bash
cd apps/backend && PYTHONPATH=. uv run pytest tests/test_security/test_staging_health_wiring.py -q -p no:cacheprovider -W ignore --no-header -rA 2>/dev/null | grep -E "^PASSED|passed|failed"
```

```output
PASSED tests/test_security/test_staging_health_wiring.py::test_runbook_names_every_secret_the_compose_file_interpolates
PASSED tests/test_security/test_staging_health_wiring.py::test_scheduled_probe_runs_independently_of_deploys
PASSED tests/test_security/test_staging_health_wiring.py::test_deploy_gate_asserts_connection_dependent_health
```

**AC4, deploy path.** The deploy gate no longer curls bare `/health`: it waits on `/health/ready` (503 until the service's own pool authenticates) and then runs the probe inside the container that `up -d` just recreated, so every connection it makes is new. The manual rotation path in the runbook is the same two steps (`up -d --force-recreate`, then the probe):

```bash
sed -n "/- name: Health check/,/python -m app.health_probe\"/p" .github/workflows/deploy.yml; echo; grep -nE "force-recreate|python -m app.health_probe|never" docs/operations/CREDENTIAL_ROTATION.md
```

```output
      - name: Health check
        if: steps.preflight.outputs.configured == 'true'
        env:
          HOST: ${{ secrets.HOST }}
          DEPLOY_USER: ${{ secrets.DEPLOY_USER || 'root' }}
          DEPLOY_PATH: ${{ secrets.DEPLOY_PATH || '/opt/narrative-modeling-app/staging' }}
        run: |
          # Wait on /health/ready (Mongo-backed: 503 until the service's pool
          # authenticates) — NOT bare /health, which answers 200 from a worker whose
          # credentials are dead — then run the per-subsystem probe inside the
          # container `up -d` just recreated. Every connection the probe makes is
          # therefore fresh: this is the restart-after-rotation smoke step of #552.
          # Backend is exposed on host port 8010 (see compose).
          ssh -i ~/.ssh/staging_key -o BatchMode=yes "$DEPLOY_USER@$HOST" \
            "set -e
             for i in \$(seq 1 12); do
               if curl -fsS http://localhost:8010/health/ready >/dev/null; then
                 echo 'Backend ready.'; break
               fi
               if [ \$i -eq 12 ]; then echo 'Backend did not become ready in time.'; exit 1; fi
               echo \"Waiting for backend readiness (\$i/12)...\"; sleep 10
             done
             cd '$DEPLOY_PATH'
             docker compose -f docker-compose.staging.yml --env-file .env.staging exec -T backend python -m app.health_probe"

56:3. **Recreate the consumers.** Compose injects env at creation, so never
60:   docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --force-recreate backend frontend
63:   `--force-recreate` is deliberate: `up -d` alone recreates only when it sees a
69:   docker compose -f docker-compose.staging.yml --env-file .env.staging exec -T backend python -m app.health_probe
```

The probe's own contract is covered by `tests/test_scripts/test_health_probe.py` (ten tests; two against the real app and a real Mongo over ASGITransport, one of them the stale-URI case above). Ten mutations — exit 0 on failure, ignoring the HTTP code, dropping the per-subsystem statuses, a fresh ping that never connects, a malformed check entry relabelling `ready`, a list-shaped `checks` raising, the deploy gate back on `/health`, a secret removed from the runbook, the schedule removed, the issue report gated back on the probe step's own outcome — each fail exactly the test written for them.

```bash
cd apps/backend && PYTHONPATH=. uv run pytest tests/test_scripts/test_health_probe.py -q -p no:cacheprovider -W ignore --no-header -rA 2>/dev/null | grep -E "^PASSED|passed|failed"
```

```output
PASSED tests/test_scripts/test_health_probe.py::test_every_subsystem_healthy_exits_zero
PASSED tests/test_scripts/test_health_probe.py::test_dead_s3_behind_a_ready_200_is_a_failure
PASSED tests/test_scripts/test_health_probe.py::test_not_ready_503_names_mongodb
PASSED tests/test_scripts/test_health_probe.py::test_not_configured_counts_as_failure
PASSED tests/test_scripts/test_health_probe.py::test_unreachable_service_and_raising_check_are_failures_not_crashes
PASSED tests/test_scripts/test_health_probe.py::test_malformed_check_entry_does_not_relabel_a_reached_service
PASSED tests/test_scripts/test_health_probe.py::test_non_dict_checks_value_never_raises
PASSED tests/test_scripts/test_health_probe.py::test_missing_mongodb_uri_reads_as_a_config_gap
PASSED tests/test_scripts/test_health_probe.py::test_parses_the_real_readiness_response
PASSED tests/test_scripts/test_health_probe.py::test_stale_mongo_uri_fails_even_while_the_service_pool_is_fine
```
