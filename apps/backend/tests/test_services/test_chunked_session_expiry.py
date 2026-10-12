"""#584: a chunked-upload session past its expiry is over, and the sweep finds the ones
a restart left on disk.

Only `resume` compared `expires_at` with the clock, so an expired session could still be
appended to and completed. And the sweep walked the in-memory store only: a session
written before a restart is on disk and not in the store, so its files were never reaped.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.security.upload_handler import ChunkedUploadHandler

pytestmark = pytest.mark.asyncio

OWNER = "owner_584"


async def _session(handler: ChunkedUploadHandler, *, expired: bool, complete: bool = False) -> str:
    """A session with its first chunk on disk; optionally past its expiry."""
    started = await handler.init_upload(OWNER, "visits.csv", 4)
    session_id = started["session_id"]
    await handler.upload_chunk(session_id, OWNER, 0, b"a,b\n")
    session = handler.sessions[session_id]
    if not complete:
        session["status"], session["uploaded_chunks"] = "initialized", []
    if expired:
        session["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    handler._save_session_metadata(session_id, session)
    return session_id


def _files(temp_dir: Path, session_id: str) -> list[bool]:
    return [(temp_dir / f"{session_id}{suffix}").exists() for suffix in (".tmp", ".json")]


class TestAnExpiredSessionCannotBeUsed:
    async def test_a_chunk_is_refused_and_not_written(self, tmp_path):
        handler = ChunkedUploadHandler(temp_dir=str(tmp_path))
        session_id = await _session(handler, expired=True)

        with pytest.raises(HTTPException) as refused:
            await handler.upload_chunk(session_id, OWNER, 0, b"x,y\n")

        assert refused.value.status_code == 410
        assert (tmp_path / f"{session_id}.tmp").read_bytes() == b"a,b\n"

    async def test_it_cannot_be_completed(self, tmp_path):
        handler = ChunkedUploadHandler(temp_dir=str(tmp_path))
        session_id = await _session(handler, expired=True, complete=True)

        with pytest.raises(HTTPException) as refused:
            handler.claim_upload(session_id, OWNER)

        assert refused.value.status_code == 410

    async def test_resume_still_says_expired(self, tmp_path):
        handler = ChunkedUploadHandler(temp_dir=str(tmp_path))
        session_id = await _session(handler, expired=True)

        with pytest.raises(HTTPException) as refused:
            await handler.resume_upload(session_id, OWNER)

        assert refused.value.status_code == 410

    async def test_someone_elses_expired_session_is_still_just_not_found(self, tmp_path):
        """410 for the owner only: for anyone else it would confirm the id exists (#454)."""
        handler = ChunkedUploadHandler(temp_dir=str(tmp_path))
        session_id = await _session(handler, expired=True)

        assert handler.get_session(session_id, "someone_else") is None

    async def test_it_can_still_be_aborted(self, tmp_path):
        handler = ChunkedUploadHandler(temp_dir=str(tmp_path))
        session_id = await _session(handler, expired=True)

        assert handler.abort_upload(session_id, OWNER) is True
        assert _files(tmp_path, session_id) == [False, False]

    async def test_a_live_session_is_untouched_by_all_this(self, tmp_path):
        handler = ChunkedUploadHandler(temp_dir=str(tmp_path))
        session_id = await _session(handler, expired=False)

        result = await handler.upload_chunk(session_id, OWNER, 0, b"a,b\n")

        assert result["status"] == "uploaded"


class TestTheSweepAfterARestart:
    """A new handler on the same directory is what a restarted worker is."""

    async def test_an_expired_session_left_on_disk_is_reaped(self, tmp_path):
        session_id = await _session(ChunkedUploadHandler(temp_dir=str(tmp_path)), expired=True)
        restarted = ChunkedUploadHandler(temp_dir=str(tmp_path))
        assert restarted.sessions == {} and _files(tmp_path, session_id) == [True, True]

        owners = restarted.cleanup_expired_sessions()

        assert owners == [OWNER]
        assert _files(tmp_path, session_id) == [False, False]

    async def test_a_live_session_left_on_disk_is_kept_and_not_cached(self, tmp_path):
        """Another worker may own it: a copy cached here would go stale as that worker
        records chunks."""
        session_id = await _session(ChunkedUploadHandler(temp_dir=str(tmp_path)), expired=False)
        restarted = ChunkedUploadHandler(temp_dir=str(tmp_path))

        assert restarted.cleanup_expired_sessions() == []
        assert _files(tmp_path, session_id) == [True, True]
        assert restarted.sessions == {}

    async def test_other_json_in_the_directory_is_left_alone(self, tmp_path):
        (tmp_path / "notes.json").write_text(json.dumps({"hello": "world"}))
        (tmp_path / "broken.json").write_text("{not json")
        (tmp_path / "list.json").write_text("[1, 2]")

        assert ChunkedUploadHandler(temp_dir=str(tmp_path)).cleanup_expired_sessions() == []
        assert sorted(p.name for p in tmp_path.iterdir()) == ["broken.json", "list.json", "notes.json"]

    async def test_a_session_in_memory_is_reaped_once(self, tmp_path):
        handler = ChunkedUploadHandler(temp_dir=str(tmp_path))
        session_id = await _session(handler, expired=True)

        assert handler.cleanup_expired_sessions() == [OWNER]
        assert handler.sessions == {} and _files(tmp_path, session_id) == [False, False]
