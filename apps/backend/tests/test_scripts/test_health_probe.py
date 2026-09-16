"""#552: the probe fails on a dead subsystem that ``/health/ready`` reports around.

Staging's S3 bucket was 404 for weeks while ``/health/ready`` said ``ready`` — it is
Mongo-only by design (#503). The probe is what the scheduled workflow and the
post-deploy gate run, so it must assert on every per-subsystem status, never on
the HTTP code alone.
"""

import httpx
import pytest

from app import health_probe
from app.main import app


def _ready_transport(status_code: int, checks: dict) -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(status_code, json={"status": "x", "checks": checks})
    )


async def _healthy() -> dict:
    return {"status": "healthy", "latency_ms": 1.0}


async def _unhealthy() -> dict:
    return {"status": "unhealthy", "latency_ms": 1.0, "error": "unavailable"}


async def _not_configured() -> dict:
    return {"status": "not_configured", "latency_ms": 0}


async def _raising() -> dict:
    raise RuntimeError("boom")


@pytest.fixture
def s3_openai(monkeypatch):
    def _set(s3, openai):
        monkeypatch.setattr(health_probe, "check_s3_access", s3)
        monkeypatch.setattr(health_probe, "check_openai_api", openai)

    return _set


def test_every_subsystem_healthy_exits_zero(s3_openai, capsys):
    s3_openai(_healthy, _healthy)
    transport = _ready_transport(200, {"mongodb": {"status": "healthy"}})
    assert health_probe.main(transport=transport) == 0
    out = capsys.readouterr().out
    for line in ("ready: healthy", "mongodb: healthy", "s3: healthy", "openai: healthy"):
        assert line in out
    assert "OK" in out


def test_dead_s3_behind_a_ready_200_is_a_failure(s3_openai, capsys):
    """The exact #552 scenario: readiness green, the bucket gone."""
    s3_openai(_unhealthy, _healthy)
    transport = _ready_transport(200, {"mongodb": {"status": "healthy"}})
    assert health_probe.main(transport=transport) == 1
    out = capsys.readouterr().out
    assert "s3: unhealthy" in out
    assert "FAIL: s3" in out


def test_not_ready_503_names_mongodb(s3_openai, capsys):
    s3_openai(_healthy, _healthy)
    transport = _ready_transport(503, {"mongodb": {"status": "unhealthy"}})
    assert health_probe.main(transport=transport) == 1
    out = capsys.readouterr().out
    assert "ready: http 503" in out
    assert "mongodb: unhealthy" in out
    assert "FAIL: mongodb, ready" in out


def test_not_configured_counts_as_failure(s3_openai):
    """Staging must have S3 and OpenAI; mock mode there is a misconfiguration."""
    s3_openai(_healthy, _not_configured)
    transport = _ready_transport(200, {"mongodb": {"status": "healthy"}})
    assert health_probe.main(transport=transport) == 1


def test_unreachable_service_and_raising_check_are_failures_not_crashes(s3_openai, capsys):
    s3_openai(_raising, _healthy)

    def _refuse(request):
        raise httpx.ConnectError("refused")

    assert health_probe.main(transport=httpx.MockTransport(_refuse)) == 1
    out = capsys.readouterr().out
    assert "ready: unreachable (ConnectError)" in out
    assert "s3: unreachable (RuntimeError)" in out


@pytest.mark.asyncio
async def test_parses_the_real_readiness_response(setup_database, s3_openai):
    """Against the real app and a real Mongo: the shape the probe reads is the shape
    ``/health/ready`` actually returns."""
    s3_openai(_healthy, _healthy)
    statuses = await health_probe.probe(transport=httpx.ASGITransport(app=app))
    assert statuses["ready"] == "healthy"
    assert statuses["mongodb"] == "healthy"
