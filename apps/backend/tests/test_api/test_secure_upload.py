"""
Tests for Secure Upload API endpoints
"""

import io
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.models.user_data import UserData


class TestCleanupEndpointAuth:
    """/cleanup now requires authentication (issue #272)."""

    async def test_cleanup_requires_auth(self):
        """An unauthenticated GET /cleanup is rejected (was open to any caller)."""
        # Build an app WITHOUT the auth dependency override so the real
        # HTTPBearer runs and rejects the missing credential.
        from app.api.routes import secure_upload

        app = FastAPI()
        app.include_router(secure_upload.router, prefix="/api/v1/upload")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/upload/cleanup")

        # HTTPBearer returns 401 for a missing credential (post-starlette bump).
        assert response.status_code == 401

    async def test_cleanup_succeeds_when_authenticated(
        self, mock_async_client: AsyncClient, mock_upload_handler
    ):
        """With a valid identity the reaper runs and returns the cleaned count."""
        # The reaper returns the owner id of each session it reaped, so their
        # concurrency slots can be handed back (issue #526).
        mock_upload_handler.cleanup_expired_sessions.return_value = ["a", "b", "c"]

        response = await mock_async_client.get("/api/v1/upload/cleanup")

        assert response.status_code == 200
        assert response.json() == {"cleaned_sessions": 3}
        mock_upload_handler.cleanup_expired_sessions.assert_called_once()


class TestSecureUploadAPI:
    """Exercises the REAL /upload/secure path — real ``UserData`` insert, real PII
    detection, real schema inference — faking ONLY the external S3 boundary and the
    background AI-summary task, with ``autospec=True`` so a wrong call signature is
    caught (#492). The previous version ran against a patched-out ``UserData`` model
    (``mock_user_data``), so it asserted 200 over code that never touched the
    database and could not have caught a validation/persistence failure.

    ``setup_database`` gives a real (test) Mongo: the route is quota-metered (#368)
    and writes a document, both of which need a live database.
    """

    def _s3_ok(self):
        return patch(
            "app.api.routes.secure_upload.upload_file_to_s3",
            autospec=True,
            return_value=(True, "s3://test-bucket/datasets/test_user_123/f.csv"),
        )

    def _summary_stub(self):
        # /upload/secure schedules a background task that hits OpenAI. It does a
        # LOCAL `from app.utils.ai_summary import generate_dataset_summary`, so the
        # symbol resolved at call time is app.utils.ai_summary.generate_dataset_summary
        # — patch THAT (autospec, so a signature change is caught) to keep this
        # route test off the network. Starlette runs BackgroundTasks synchronously
        # under ASGITransport, so an un-stubbed task really would call OpenAI here.
        return patch(
            "app.utils.ai_summary.generate_dataset_summary", autospec=True
        )

    async def test_secure_upload_no_pii(self, setup_database, async_authorized_client):
        """Clean data → 200, and a REAL UserData document is persisted."""
        csv_data = "product_id,price,category\n1001,19.99,electronics\n1002,29.99,books"
        files = {"file": ("clean.csv", io.BytesIO(csv_data.encode()), "text/csv")}
        with self._s3_ok(), self._summary_stub():
            response = await async_authorized_client.post(
                "/api/v1/upload/secure", files=files
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "success"
        assert data["pii_report"]["has_pii"] is False
        assert "file_id" in data
        doc = await UserData.find_one(
            UserData.user_id == "test_user_123", UserData.filename == "clean.csv"
        )
        assert doc is not None
        assert doc.num_rows == 2 and doc.num_columns == 3
        assert doc.contains_pii is False

    async def test_secure_upload_with_pii(self, setup_database, async_authorized_client):
        """A PII-named column holding real PII values is high risk → the caller must
        confirm; nothing is stored yet (#608). Exercises the real PIIDetector."""
        csv_data = "name,email,phone\nJohn Doe,john@example.com,555-1234"
        files = {"file": ("pii.csv", io.BytesIO(csv_data.encode()), "text/csv")}
        with self._s3_ok(), self._summary_stub():
            response = await async_authorized_client.post(
                "/api/v1/upload/secure", files=files
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "pii_detected"
        assert data["requires_confirmation"] is True
        assert data["pii_report"]["risk_level"] == "high"
        # High-risk PII is gated: no document was created.
        assert await UserData.find_one(UserData.filename == "pii.csv") is None

    async def test_secure_upload_with_pii_named_columns_but_plain_values(
        self, setup_database, async_authorized_client
    ):
        """A label alone is a hint, not proof: medium risk → stored without the gate,
        and a real document is written (#608/#492)."""
        csv_data = "name,email,phone\nJohn Doe,not provided,unknown"
        files = {"file": ("names.csv", io.BytesIO(csv_data.encode()), "text/csv")}
        with self._s3_ok(), self._summary_stub():
            response = await async_authorized_client.post(
                "/api/v1/upload/secure", files=files
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "success"
        assert data["pii_report"]["has_pii"] is True
        assert data["pii_report"]["risk_level"] == "medium"
        doc = await UserData.find_one(
            UserData.user_id == "test_user_123", UserData.filename == "names.csv"
        )
        assert doc is not None and doc.contains_pii is True

    async def test_secure_upload_invalid_file(self, setup_database, async_authorized_client):
        """A non-CSV/Excel file is a 400 before any S3 or DB work."""
        files = {"file": ("bad.txt", io.BytesIO(b"not a csv"), "text/plain")}
        with self._s3_ok(), self._summary_stub():
            response = await async_authorized_client.post(
                "/api/v1/upload/secure", files=files
            )
        assert response.status_code == 400
        assert "detail" in response.json()

    # The chunked-upload route tests live in tests/test_api/test_chunked_upload_flow.py
    # (issues #454/#462/#463/#464) and run against a real handler + database.
    # Removed test_upload_metrics_tracking (issue #273): metrics are Prometheus at
    # GET /metrics (tests/test_middleware/test_metrics.py).


class TestChunkedCompletionSizeCap:
    """Issue #270: chunked upload completion must not read an oversized assembled
    file into memory (chunked sessions allow very large files)."""

    async def test_chunked_completion_rejects_oversized_file_413(self, tmp_path, monkeypatch):
        from unittest.mock import patch

        import pytest
        from fastapi import BackgroundTasks, HTTPException

        from app.api.routes import secure_upload

        monkeypatch.setattr(secure_upload, "MAX_UPLOAD_BYTES", 10)
        assembled = tmp_path / "assembled.csv"
        assembled.write_bytes(b"x" * 5000)  # 5 KB, over the 10 B cap

        with patch.object(
            secure_upload.upload_handler,
            "claim_upload",
            return_value={
                "user_id": "u1",
                "filename": "assembled.csv",
                "temp_path": str(assembled),
            },
        ):
            with pytest.raises(HTTPException) as exc:
                await secure_upload.complete_chunked_upload(
                    session_id="s1",
                    background_tasks=BackgroundTasks(),
                    current_user_id="u1",
                )

        assert exc.value.status_code == 413
        assert not assembled.exists()  # oversized temp file cleaned up, not read
