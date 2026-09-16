"""Per-subsystem staging probe (#552): ``python -m app.health_probe``.

``/health`` is liveness and ``/health/ready`` is deliberately MongoDB-only (#503),
so neither says anything about S3 or OpenAI — the staging bucket was 404 for
weeks while every automated signal stayed green. The scheduled
``staging-health.yml`` workflow and the post-deploy gate in ``deploy.yml`` run
this inside the backend container, where it:

* GETs ``/health/ready`` on the RUNNING service — proves the workers booted and
  the service's own Mongo pool authenticates;
* opens a brand-new Mongo connection (``mongodb_fresh``) and runs
  ``check_s3_access`` / ``check_openai_api`` in THIS fresh process with the
  container's env — new connections each run, so a stale credential fails here
  the moment the env file is wrong, not at the next restart. The service's own
  pool authenticated before any rotation and keeps working until then (SCRAM is
  per connection), which is exactly how the Atlas rotation hid for three weeks.

Exit 0 only when every status is ``healthy``. ``not_configured`` is a failure on
purpose: staging must have S3 and OpenAI (upload is the first product step).
"""

import asyncio
import os
import sys
from typing import Any

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.routes.health import check_openai_api, check_s3_access

DEFAULT_URL = "http://localhost:8000"
MONGO_TIMEOUT_MS = 10_000


async def _fresh_mongo_ping() -> dict[str, Any]:
    """Ping Mongo over a connection created right now, from ``MONGODB_URI``."""
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        return {"status": "not_configured"}  # a config gap, not a network one
    client: AsyncIOMotorClient[Any] = AsyncIOMotorClient(
        uri, serverSelectionTimeoutMS=MONGO_TIMEOUT_MS
    )
    try:
        await client.admin.command("ping")
    finally:
        client.close()
    return {"status": "healthy"}


async def _ready(
    base_url: str, transport: httpx.AsyncBaseTransport | None
) -> tuple[int, dict[str, Any]]:
    async with httpx.AsyncClient(base_url=base_url, transport=transport, timeout=10.0) as client:
        response = await client.get("/health/ready")
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body if isinstance(body, dict) else {}


async def probe(
    base_url: str = DEFAULT_URL, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, str]:
    """Status per subsystem. Never raises: a check that blows up is reported as
    ``unreachable``, which fails the probe like any other non-``healthy`` status."""
    statuses: dict[str, str] = {}
    body: dict[str, Any] = {}
    try:
        code, body = await _ready(base_url, transport)
    except Exception as exc:
        statuses["ready"] = f"unreachable ({type(exc).__name__})"
    else:
        statuses["ready"] = "healthy" if code == 200 else f"http {code}"
    # Parsed outside the try so a malformed entry can't relabel a reached service.
    for name, check in (body.get("checks") or {}).items():
        statuses[name] = str(check.get("status")) if isinstance(check, dict) else str(check)
    fresh = (
        ("mongodb_fresh", _fresh_mongo_ping),
        ("s3", check_s3_access),
        ("openai", check_openai_api),
    )
    for name, check_fn in fresh:
        try:
            statuses[name] = str((await check_fn()).get("status"))
        except Exception as exc:
            statuses[name] = f"unreachable ({type(exc).__name__})"
    return statuses


def main(transport: httpx.AsyncBaseTransport | None = None) -> int:
    statuses = asyncio.run(probe(os.getenv("HEALTH_PROBE_URL", DEFAULT_URL), transport))
    for name, status in statuses.items():
        print(f"{name}: {status}")
    failing = sorted(name for name, status in statuses.items() if status != "healthy")
    if failing:
        print(f"FAIL: {', '.join(failing)}")
        return 1
    print("OK: every dependency healthy")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
