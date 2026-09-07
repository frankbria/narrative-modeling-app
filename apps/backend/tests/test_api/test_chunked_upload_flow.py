"""Real-flow tests for the chunked-upload surface.

Issues #463 (init unreachable), #462 (completion 500s), #464 (unprefixed,
client-derived S3 key) and #454 (sessions not bound to a user).

These deliberately do NOT use ``tests/test_api/conftest.py``'s
``mock_upload_handler``/``mock_user_data``: those patch out the handler and the
``UserData`` model, which is how ``test_chunked_upload_complete`` asserted 200
against a route that could not succeed against a real database for as long as it
existed. Everything below runs the real handler and inserts a real document; only
the S3 call is substituted, and it records the key it was given so the
tenant-prefix invariant can be asserted directly.
"""

import io
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

from app.api.routes import secure_upload as secure_upload_module
from app.models.user_data import UserData

CSV = b"id,name,score\n1,alice,10\n2,bob,20\n"

TENANT_A = "tenant_a_user"
TENANT_B = "tenant_b_user"


@pytest.fixture
def s3_calls(monkeypatch):
    """Substitute upload_file_to_s3, recording (key, content_type) per call."""
    calls: list[tuple[str, str | None]] = []

    def fake_upload(content: bytes, s3_filename: str, content_type: str | None = None):
        calls.append((s3_filename, content_type))
        return True, f"s3://test-bucket/{s3_filename}"

    monkeypatch.setattr(secure_upload_module, "upload_file_to_s3", fake_upload)
    return calls


@pytest.fixture
def fresh_handler(tmp_path, monkeypatch):
    """A handler with its own temp dir, so sessions never leak between tests."""
    from app.services.security.upload_handler import ChunkedUploadHandler

    handler = ChunkedUploadHandler(temp_dir=str(tmp_path / "uploads"))
    monkeypatch.setattr(secure_upload_module, "upload_handler", handler)
    return handler


@pytest_asyncio.fixture
async def client_as(setup_database) -> AsyncGenerator:
    """Yield a factory producing an authorized client for a given tenant id.

    ``async_authorized_client`` is pinned to one user; cross-tenant assertions
    need two, and they must reach the same app instance so they share the
    in-process session store.
    """
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    from app.auth.nextauth_auth import get_current_user_id
    from app.main import app
    from tests.conftest import _point_app_at_test_database

    current = {"user_id": TENANT_A}

    async def override() -> str:
        return current["user_id"]

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user_id] = override

    _point_app_at_test_database()
    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            def as_tenant(user_id: str) -> AsyncClient:
                current["user_id"] = user_id
                return client

            yield as_tenant

    app.dependency_overrides.clear()


async def _init(client, filename="data.csv", file_size=len(CSV)):
    """Init a session the way the browser client does — a form body."""
    return await client.post(
        "/api/v1/upload/chunked/init",
        data={"filename": filename, "file_size": str(file_size)},
    )


async def _upload_all(client, session_id, content=CSV):
    return await client.post(
        f"/api/v1/upload/chunked/{session_id}/chunk/0",
        files={"file": ("chunk0", io.BytesIO(content), "application/octet-stream")},
    )


class TestInitAcceptsTheClientsRequest:
    """#463: init declared query params while the client posts a form body."""

    async def test_form_body_init_succeeds(self, client_as, fresh_handler):
        response = await _init(client_as(TENANT_A))

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_chunks"] == 1
        assert body["session_id"]

    async def test_missing_required_field_is_422(self, client_as, fresh_handler):
        response = await client_as(TENANT_A).post(
            "/api/v1/upload/chunked/init", data={"filename": "data.csv"}
        )

        assert response.status_code == 422

    async def test_zero_file_size_is_400_not_a_later_500(
        self, client_as, fresh_handler
    ):
        """total_chunks would be 0, and resume then divides by it."""
        response = await _init(client_as(TENANT_A), file_size=0)

        assert response.status_code == 400

    async def test_oversize_init_is_413(self, client_as, fresh_handler):
        response = await _init(
            client_as(TENANT_A), file_size=200 * 1024 * 1024 * 1024
        )

        assert response.status_code == 413


class TestSessionIdsAreUnguessable:
    """#454 AC3."""

    async def test_ids_are_high_entropy_and_unique(self, client_as, fresh_handler):
        ids = set()
        for i in range(3):
            response = await _init(client_as(TENANT_A), filename=f"f{i}.csv")
            assert response.status_code == 200
            ids.add(response.json()["session_id"])

        assert len(ids) == 3
        # secrets.token_urlsafe(32) — the old sha256(filename:size:timestamp)[:16]
        # was both shorter and derived entirely from guessable inputs.
        assert all(len(sid) > 32 for sid in ids)

    async def test_identical_inputs_still_yield_distinct_ids(
        self, client_as, fresh_handler
    ):
        first = await _init(client_as(TENANT_A), filename="same.csv")
        second = await _init(client_as(TENANT_A), filename="same.csv")

        assert first.json()["session_id"] != second.json()["session_id"]


class TestCompletionStoresAUsableDataset:
    """#462: wrong S3 arity, a tuple in s3_url, and a missing required field."""

    async def test_complete_inserts_a_real_user_data_document(
        self, client_as, fresh_handler, s3_calls
    ):
        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]
        assert (await _upload_all(client, session_id)).json()["complete"] is True

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/complete"
        )

        assert response.status_code == 200, response.text
        file_id = response.json()["file_id"]

        stored = await UserData.get(file_id)
        assert stored is not None
        # The bug assigned the (success, url) tuple straight to this str field.
        assert isinstance(stored.s3_url, str)
        assert stored.s3_url.startswith("s3://")
        assert stored.original_filename == "data.csv"  # was omitted entirely
        assert stored.num_rows == 2
        assert stored.num_columns == 3
        assert stored.file_type == "csv"

    async def test_a_repeated_complete_is_404_not_500(
        self, client_as, fresh_handler, s3_calls
    ):
        """The first complete unlinks the temp file; the second used to stat() it."""
        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]
        await _upload_all(client, session_id)

        first = await client.post(f"/api/v1/upload/chunked/{session_id}/complete")
        second = await client.post(f"/api/v1/upload/chunked/{session_id}/complete")

        assert first.status_code == 200, first.text
        assert second.status_code == 404
        assert len(s3_calls) == 1  # and no duplicate object was written

    async def test_two_concurrent_completes_produce_one_dataset(
        self, client_as, fresh_handler, s3_calls
    ):
        """Both used to pass the session checks before either finished.

        The result was two S3 objects, two UserData rows and two charged quota
        units — and both returned 200, so the refund middleware credited nothing.
        """
        import asyncio

        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]
        await _upload_all(client, session_id)

        first, second = await asyncio.gather(
            client.post(f"/api/v1/upload/chunked/{session_id}/complete"),
            client.post(f"/api/v1/upload/chunked/{session_id}/complete"),
        )

        assert sorted([first.status_code, second.status_code]) == [200, 404]
        assert len(s3_calls) == 1
        assert await UserData.find(UserData.user_id == TENANT_A).count() == 1

    async def test_corrupt_csv_is_400_not_500(
        self, client_as, fresh_handler, s3_calls
    ):
        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]
        # Ragged rows: pandas raises rather than returning a frame.
        await _upload_all(client, session_id, content=b'a,b\n1,2\n3,4,5,6,7\n')

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/complete"
        )

        assert response.status_code == 400
        assert s3_calls == []

    async def test_unsupported_extension_is_400_not_500(
        self, client_as, fresh_handler, s3_calls
    ):
        client = client_as(TENANT_A)
        session_id = (await _init(client, filename="notes.txt")).json()["session_id"]
        await _upload_all(client, session_id, content=b"not a table")

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/complete"
        )

        assert response.status_code == 400


class TestS3KeysAreServerDerivedAndTenantScoped:
    """#464."""

    async def test_key_is_prefixed_and_ignores_the_client_filename(
        self, client_as, fresh_handler, s3_calls
    ):
        client = client_as(TENANT_A)
        session_id = (
            await _init(client, filename="../../etc/passwd.csv")
        ).json()["session_id"]
        await _upload_all(client, session_id)

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/complete"
        )

        assert response.status_code == 200, response.text
        key, content_type = s3_calls[-1]
        assert key.startswith(f"datasets/{TENANT_A}/")
        assert "passwd" not in key
        assert ".." not in key
        # user_id used to be passed positionally into the content_type slot.
        assert content_type == "text/csv"

    async def test_two_tenants_uploading_the_same_name_do_not_collide(
        self, client_as, fresh_handler, s3_calls
    ):
        file_ids = {}
        for tenant in (TENANT_A, TENANT_B):
            client = client_as(tenant)
            session_id = (
                await _init(client, filename="data.csv")
            ).json()["session_id"]
            await _upload_all(client, session_id)
            response = await client.post(
                f"/api/v1/upload/chunked/{session_id}/complete"
            )
            assert response.status_code == 200, response.text
            file_ids[tenant] = response.json()["file_id"]

        keys = [key for key, _ in s3_calls]
        assert len(set(keys)) == 2
        assert keys[0].startswith(f"datasets/{TENANT_A}/")
        assert keys[1].startswith(f"datasets/{TENANT_B}/")

        # Both datasets survive and stay readable — the collision destroyed one.
        for tenant, file_id in file_ids.items():
            stored = await UserData.get(file_id)
            assert stored is not None
            assert stored.user_id == tenant


class TestChunkedIngestionIsMetered:
    """The chunked route creates datasets exactly like /secure, so it has to
    reserve `uploads` quota too. Pre-fix this route had no quota dependency —
    harmless only because completion always 500'd before inserting anything."""

    async def test_completing_an_upload_charges_the_uploads_counter(
        self, client_as, fresh_handler, s3_calls
    ):
        from app.billing.metering import period_key_for
        from app.models.usage import UsageRecord

        async def used() -> int:
            row = await UsageRecord.find_one(
                UsageRecord.user_id == TENANT_A,
                UsageRecord.period_key == period_key_for(),
                UsageRecord.metric == "uploads",
            )
            return row.units if row else 0

        before = await used()

        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]
        await _upload_all(client, session_id)
        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/complete"
        )

        assert response.status_code == 200, response.text
        assert await used() == before + 1


    async def test_a_failed_complete_refunds_the_reserved_unit(
        self, client_as, fresh_handler, s3_calls
    ):
        """Reserving at complete is only safe if failure gives the unit back.

        QuotaRefundMiddleware credits any >=400, but the choice to reserve here
        rather than at init rests on that, so pin it directly.
        """
        from app.billing.metering import period_key_for
        from app.models.usage import UsageRecord

        async def used() -> int:
            row = await UsageRecord.find_one(
                UsageRecord.user_id == TENANT_A,
                UsageRecord.period_key == period_key_for(),
                UsageRecord.metric == "uploads",
            )
            return row.units if row else 0

        before = await used()

        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]
        await _upload_all(client, session_id, content=b"a,b\n1,2\n3,4,5,6\n")

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/complete"
        )

        assert response.status_code == 400, response.text
        assert await used() == before


class TestChunkHashIsReadFromTheFormBody:
    """Same class as #463: an undecorated parameter on a multipart route is a
    query param, so a client sending it in the body would be silently ignored."""

    async def test_a_matching_hash_in_the_form_body_is_accepted(
        self, client_as, fresh_handler
    ):
        import hashlib

        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/chunk/0",
            files={"file": ("chunk0", io.BytesIO(CSV), "application/octet-stream")},
            data={"chunk_hash": hashlib.md5(CSV).hexdigest()},
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "uploaded"

    async def test_a_mismatched_hash_in_the_form_body_is_rejected(
        self, client_as, fresh_handler
    ):
        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/chunk/0",
            files={"file": ("chunk0", io.BytesIO(CSV), "application/octet-stream")},
            data={"chunk_hash": "0" * 32},
        )

        assert response.status_code == 400
        assert "hash mismatch" in response.json()["detail"].lower()


class TestUppercaseExtensionsAreAccepted:
    """`data.CSV` is a legitimate filename; the dispatch was case-sensitive."""

    async def test_an_uppercase_extension_completes(
        self, client_as, fresh_handler, s3_calls
    ):
        client = client_as(TENANT_A)
        session_id = (await _init(client, filename="DATA.CSV")).json()["session_id"]
        await _upload_all(client, session_id)

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/complete"
        )

        assert response.status_code == 200, response.text
        key, content_type = s3_calls[-1]
        assert key.endswith(".csv")  # the key extension is normalised
        assert content_type == "text/csv"


class TestConcurrencySlotAccounting:
    """One start_upload per session must be matched by exactly one release."""

    async def test_completing_an_upload_releases_exactly_one_slot(
        self, client_as, fresh_handler, s3_calls
    ):
        from app.api.routes.secure_upload import rate_limiter

        rate_limiter.active_uploads.pop(TENANT_A, None)

        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]
        assert rate_limiter.active_uploads[TENANT_A] == 1

        await _upload_all(client, session_id)
        # The chunk route used to release here too, which drove the count to 0
        # and left the 10-concurrent cap permanently unbindable.
        assert rate_limiter.active_uploads[TENANT_A] == 1

        assert (
            await client.post(f"/api/v1/upload/chunked/{session_id}/complete")
        ).status_code == 200
        assert rate_limiter.active_uploads[TENANT_A] == 0


class TestFailureStillReleasesTheConcurrencySlot:
    """A failed complete used to hold its slot forever.

    Releasing only on the success path meant ten corrupt uploads pinned a user
    at the concurrency cap, with the session already gone so DELETE could not
    recover it — every subsequent init 429'd until the worker restarted.
    """

    async def test_a_failed_complete_does_not_hold_the_slot(
        self, client_as, fresh_handler, s3_calls
    ):
        from app.api.routes.secure_upload import rate_limiter

        rate_limiter.active_uploads.pop(TENANT_A, None)
        client = client_as(TENANT_A)

        for _ in range(3):
            session_id = (await _init(client)).json()["session_id"]
            await _upload_all(client, session_id, content=b"a,b\n1,2\n3,4,5,6\n")
            response = await client.post(
                f"/api/v1/upload/chunked/{session_id}/complete"
            )
            assert response.status_code == 400, response.text

        assert rate_limiter.active_uploads[TENANT_A] == 0

    async def test_a_failed_complete_leaves_no_temp_file(
        self, client_as, fresh_handler, s3_calls
    ):
        client = client_as(TENANT_A)
        session_id = (await _init(client, filename="notes.txt")).json()["session_id"]
        await _upload_all(client, session_id, content=b"not a table")

        assert (
            await client.post(f"/api/v1/upload/chunked/{session_id}/complete")
        ).status_code == 400
        assert list(fresh_handler.temp_dir.iterdir()) == []


class TestChunkPayloadIsBoundedByDeclaredGeometry:
    """#270's init-time cap only bounds disk usage if chunks respect it."""

    async def test_a_negative_chunk_number_is_400(self, client_as, fresh_handler):
        """An upper-bound-only check let it through to a negative seek offset."""
        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/chunk/-1",
            files={"file": ("c", io.BytesIO(b"x"), "application/octet-stream")},
        )

        assert response.status_code == 400

    async def test_a_chunk_larger_than_chunk_size_is_413(
        self, client_as, fresh_handler
    ):
        fresh_handler.chunk_size = 16
        client = client_as(TENANT_A)
        session_id = (await _init(client, file_size=16)).json()["session_id"]

        response = await _upload_all(client, session_id, content=b"x" * 4096)

        assert response.status_code == 413
        assert not (fresh_handler.temp_dir / f"{session_id}.tmp").exists()


class TestSessionsAreBoundToTheirOwner:
    """#454 AC1/AC2/AC4."""

    @pytest_asyncio.fixture
    async def a_session(self, client_as, fresh_handler):
        """A half-finished session owned by tenant A."""
        response = await _init(client_as(TENANT_A))
        assert response.status_code == 200
        return response.json()["session_id"]

    async def test_owner_is_recorded_at_creation(self, a_session, fresh_handler):
        assert fresh_handler.sessions[a_session]["user_id"] == TENANT_A

    async def test_foreign_tenant_cannot_append_a_chunk(
        self, a_session, client_as
    ):
        response = await _upload_all(
            client_as(TENANT_B), a_session, content=b"id\n999\n"
        )

        assert response.status_code == 404

    async def test_foreign_tenant_cannot_read_resume_state(
        self, a_session, client_as
    ):
        response = await client_as(TENANT_B).get(
            f"/api/v1/upload/chunked/{a_session}/resume"
        )

        assert response.status_code == 404

    async def test_foreign_tenant_cannot_complete(
        self, a_session, client_as, s3_calls
    ):
        await _upload_all(client_as(TENANT_A), a_session)

        response = await client_as(TENANT_B).post(
            f"/api/v1/upload/chunked/{a_session}/complete"
        )

        assert response.status_code == 404
        assert s3_calls == []

    async def test_foreign_tenant_cannot_abort(
        self, a_session, client_as, fresh_handler
    ):
        response = await client_as(TENANT_B).delete(
            f"/api/v1/upload/chunked/{a_session}"
        )

        assert response.status_code == 404
        # The victim's session is untouched.
        victim = await client_as(TENANT_A).get(
            f"/api/v1/upload/chunked/{a_session}/resume"
        )
        assert victim.status_code == 200

    async def test_a_foreign_session_is_indistinguishable_from_a_missing_one(
        self, a_session, client_as
    ):
        foreign = await client_as(TENANT_B).get(
            f"/api/v1/upload/chunked/{a_session}/resume"
        )
        missing = await client_as(TENANT_B).get(
            "/api/v1/upload/chunked/EhLmvS3n0tAr3alS3ss10nIdAtAllXXXXXXXXXXX/resume"
        )

        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json()

    async def test_owner_can_abort_and_the_partial_file_is_removed(
        self, a_session, client_as, fresh_handler
    ):
        client = client_as(TENANT_A)
        await _upload_all(client, a_session)
        temp_path = fresh_handler.sessions[a_session]["temp_path"]

        response = await client.delete(f"/api/v1/upload/chunked/{a_session}")

        assert response.status_code == 200
        assert response.json()["status"] == "aborted"

        from pathlib import Path

        assert not Path(temp_path).exists()
        assert (
            await client.get(f"/api/v1/upload/chunked/{a_session}/resume")
        ).status_code == 404

    async def test_session_id_cannot_escape_the_temp_directory(
        self, client_as, fresh_handler, tmp_path
    ):
        """The session id is a path param spliced into a filename under temp_dir.

        Planted as a real readable file outside temp_dir, so this fails on the
        traversal rather than on the target simply not existing.
        """
        import json

        outside = tmp_path / "outside.json"
        outside.write_text(json.dumps({"user_id": TENANT_A, "temp_path": "/x"}))
        escaping_id = f"../{outside.stem}"

        assert fresh_handler.get_session(escaping_id, TENANT_A) is None

        response = await client_as(TENANT_A).get(
            "/api/v1/upload/chunked/..%2F..%2Fetc%2Fpasswd/resume"
        )
        assert response.status_code == 404

    def test_the_session_id_allowlist_admits_nothing_outside_its_alphabet(self):
        """Asserted on the pattern, not through `get_session`.

        A malformed id is rejected by the lookup anyway — no session or file
        will ever match it — so a behavioural test cannot tell a strict
        allowlist from a loose one. This is the invariant the comment claims,
        and `^...$` with `match` did not hold it: `$` matches immediately
        before a single trailing newline.
        """
        from app.services.security.upload_handler import _SESSION_ID_RE

        assert _SESSION_ID_RE.fullmatch("aB3_-x")
        for bad in ("abc\n", "", "a" * 129, "../x", "a/b", "a.json", "a b"):
            assert not _SESSION_ID_RE.fullmatch(bad), bad


@pytest.mark.integration
class TestCompletionAgainstRealS3:
    """#462 AC5: the flow end-to-end against real object storage.

    Everything above substitutes upload_file_to_s3, so it proves the key and the
    document but not that the call itself works — which is exactly what the
    mis-ordered-argument bug broke. This drives the real boto3 path against
    LocalStack and reads the object back.
    """

    async def test_uploaded_object_is_retrievable_at_the_prefixed_key(
        self, client_as, fresh_handler, s3_client, test_s3_bucket, monkeypatch
    ):
        from app.utils import s3 as s3_module

        monkeypatch.setenv("AWS_BUCKET_NAME", test_s3_bucket)
        monkeypatch.setenv(
            "AWS_ENDPOINT_URL", os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
        )
        monkeypatch.setattr(s3_module, "s3_client", None)

        client = client_as(TENANT_A)
        session_id = (await _init(client)).json()["session_id"]
        await _upload_all(client, session_id)

        response = await client.post(
            f"/api/v1/upload/chunked/{session_id}/complete"
        )

        assert response.status_code == 200, response.text
        stored = await UserData.get(response.json()["file_id"])
        assert stored is not None

        bucket, key = s3_module.parse_s3_url(stored.s3_url)
        assert key.startswith(f"datasets/{TENANT_A}/")

        obj = s3_client.get_object(Bucket=test_s3_bucket, Key=key)
        assert obj["Body"].read() == CSV
        assert obj["ContentType"] == "text/csv"
