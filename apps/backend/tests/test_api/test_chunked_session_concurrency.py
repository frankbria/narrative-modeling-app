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


@pytest.mark.asyncio
async def test_concurrent_same_chunk_cannot_falsely_complete_a_holed_upload(tmp_path):
    """#580: two racing POSTs of the SAME not-yet-uploaded chunk must not each append
    it — a duplicate makes len(uploaded_chunks) == total_chunks fire while another
    chunk is still missing, flipping a holed session to 'complete'."""
    import asyncio

    h = ChunkedUploadHandler(temp_dir=str(tmp_path), chunk_size=10)
    user = "u580"
    init = await h.init_upload(user_id=user, filename="f.bin", file_size=30)  # 3 chunks
    sid = init["session_id"]
    assert init["total_chunks"] == 3

    # Chunk 0 lands; chunk 2 will stay missing. Race two POSTs of chunk 1.
    await h.upload_chunk(sid, user, 0, b"0123456789")
    await asyncio.gather(
        h.upload_chunk(sid, user, 1, b"aaaaaaaaaa"),
        h.upload_chunk(sid, user, 1, b"aaaaaaaaaa"),
    )

    session = h.sessions[sid]
    # Chunk 1 recorded once, not twice; chunk 2 is still missing, so NOT complete.
    assert session["uploaded_chunks"] == [0, 1], session["uploaded_chunks"]
    assert session["status"] != "complete", session["status"]
