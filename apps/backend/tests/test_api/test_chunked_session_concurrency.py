"""#526: an abandoned/expired chunked-upload session must not permanently block new
uploads. The concurrency limit is derived from LIVE sessions, not a leaky counter,
so a stale session stops counting once it expires."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.security.upload_handler import ChunkedUploadHandler


def _session(user_id: str, *, expired: bool) -> dict:
    delta = timedelta(hours=-1) if expired else timedelta(hours=1)
    return {
        "id": "s", "user_id": user_id, "status": "initialized",
        "temp_path": "/tmp/uploads/nonexistent.tmp",
        "expires_at": (datetime.now(UTC) + delta).isoformat(),
    }


@pytest.mark.unit
def test_count_active_sessions_excludes_expired():
    h = ChunkedUploadHandler(temp_dir="/tmp/uploads_test_526")
    h.sessions = {
        "a1": _session("u1", expired=False),
        "a2": _session("u1", expired=False),
        "a3": _session("u1", expired=True),   # stale — must not count
        "b1": _session("u2", expired=False),  # other tenant
    }
    assert h.count_active_sessions("u1") == 2
    assert h.count_active_sessions("u2") == 1
    assert h.count_active_sessions("nobody") == 0


TEST_USER = "test_user_123"


@pytest.fixture
def _clean_handler():
    """Reset the module-level handler's session store around the route tests."""
    from app.api.routes import secure_upload

    saved = secure_upload.upload_handler.sessions
    secure_upload.upload_handler.sessions = {}
    yield secure_upload.upload_handler
    secure_upload.upload_handler.sessions = saved


async def _init(client) -> "httpx.Response":  # noqa: F821
    return await client.post(
        "/api/v1/upload/chunked/init",
        data={"filename": "big.csv", "file_size": "1048576"},
    )


@pytest.mark.asyncio
async def test_new_upload_starts_while_stale_sessions_exist(
    setup_database, async_authorized_client, _clean_handler
):
    """AC5: a full cap of EXPIRED sessions never blocks a new upload — they are
    reaped and don't count."""
    from app.api.routes.secure_upload import rate_limiter

    cap = rate_limiter.max_concurrent_uploads
    for i in range(cap + 2):  # more than the cap, all stale
        _clean_handler.sessions[f"stale{i}"] = _session(TEST_USER, expired=True)

    resp = await _init(async_authorized_client)

    assert resp.status_code == 200, resp.text
    assert "session_id" in resp.json()
    # The stale sessions were reaped, and the new one is the only live session.
    assert _clean_handler.count_active_sessions(TEST_USER) == 1


@pytest.mark.asyncio
async def test_cap_of_live_sessions_is_rejected(
    setup_database, async_authorized_client, _clean_handler
):
    """The cap still binds for LIVE sessions (the limit isn't just removed)."""
    from app.api.routes.secure_upload import rate_limiter

    cap = rate_limiter.max_concurrent_uploads
    for i in range(cap):
        _clean_handler.sessions[f"live{i}"] = _session(TEST_USER, expired=False)

    resp = await _init(async_authorized_client)
    assert resp.status_code == 429, resp.text
