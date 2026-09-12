"""Handlers that report failure in a 200 body must not echo the exception (#637).

The #269 handler sanitises 5xx bodies; these routes answer ``200 {success: false}``
and used to put ``str(e)`` in ``error`` — S3 keys, driver text, library internals.
Each test forces an internal failure whose message carries two tokens that must
never reach the client, and checks the reference in the body is the request id
the operator can grep the logs for.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from bson import ObjectId

from app.models.dataset import DatasetMetadata
from app.models.user_data import UserData

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"
SECRET = RuntimeError("s3://secret-bucket/datasets/u1/k.parquet: boom from the driver")


def _assert_sanitized(response, error_text: str):
    assert response.status_code == 200, response.text
    assert "secret-bucket" not in response.text
    assert "boom" not in response.text
    assert response.headers["X-Request-ID"] in error_text
    assert "internal error" in error_text


class TestDataIssues:
    BASE = "/api/v1/data-issues"

    async def _dataset(self) -> UserData:
        return await UserData(
            user_id=TEST_USER, filename="d.csv", original_filename="d.csv",
            s3_url=f"https://test-bucket.s3.amazonaws.com/datasets/{TEST_USER}/d.csv",
            num_rows=6, num_columns=3, data_schema=[], file_type="csv", is_processed=True,
        ).insert()

    async def test_detect(self, async_authorized_client, setup_database):
        ds = await self._dataset()
        with patch("app.api.routes.data_issues.get_dataframe_from_s3", new_callable=AsyncMock, side_effect=SECRET):
            r = await async_authorized_client.post(
                f"{self.BASE}/detect",
                json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": False}},
            )
        body = r.json()
        assert body["success"] is False
        _assert_sanitized(r, body["error"])

    @pytest.mark.parametrize("path,extra", [
        ("preview-fix", {}),
        ("apply-fix", {"preview_mode": False}),
    ])
    async def test_preview_and_apply(self, async_authorized_client, setup_database, path, extra):
        ds = await self._dataset()
        frame = pd.DataFrame({"id": [1, 2, 2], "age": [25, None, 30]})
        with patch("app.api.routes.data_issues.get_dataframe_from_s3", new_callable=AsyncMock, return_value=frame):
            detected = (await async_authorized_client.post(
                f"{self.BASE}/detect",
                json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": False}},
            )).json()
        issue_id = next(i for i in detected["issues"] if i["suggested_fixes"])["issue_id"]
        with patch("app.api.routes.data_issues.get_dataframe_from_s3", new_callable=AsyncMock, side_effect=SECRET):
            r = await async_authorized_client.post(
                f"{self.BASE}/{path}", json={"dataset_id": str(ds.id), "issue_id": issue_id, **extra}
            )
        body = r.json()
        assert body["success"] is False
        _assert_sanitized(r, body["error"])

    async def test_batch_fix(self, async_authorized_client, setup_database):
        ds = await self._dataset()
        frame = pd.DataFrame({"id": [1, 2, 2], "age": [25, None, 30]})
        with patch("app.api.routes.data_issues.get_dataframe_from_s3", new_callable=AsyncMock, return_value=frame):
            detected = (await async_authorized_client.post(
                f"{self.BASE}/detect",
                json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": False}},
            )).json()
        issue_ids = [i["issue_id"] for i in detected["issues"]]
        with patch("app.api.routes.data_issues.get_dataframe_from_s3", new_callable=AsyncMock, side_effect=SECRET):
            r = await async_authorized_client.post(
                f"{self.BASE}/batch-fix", json={"dataset_id": str(ds.id), "issue_ids": issue_ids}
            )
        body = r.json()
        assert body["success"] is False
        _assert_sanitized(r, body["error"])

    async def test_apply_fix_failure_inside_the_engine(self, async_authorized_client, setup_database):
        """The domain branch: TransformationEngine's catch-all used to put str(e) into
        result.error, the fix engine wrapped it in OperationError.message, and the
        route returned that verbatim — a leak through the 'safe' branch."""
        ds = await self._dataset()
        frame = pd.DataFrame({"id": [1, 2, 2], "age": [25, None, 30]})
        with patch("app.api.routes.data_issues.get_dataframe_from_s3", new_callable=AsyncMock, return_value=frame):
            detected = (await async_authorized_client.post(
                f"{self.BASE}/detect",
                json={"dataset_id": str(ds.id), "options": {"include_ai_analysis": False}},
            )).json()
            issue_id = next(i for i in detected["issues"] if i["suggested_fixes"])["issue_id"]
            with patch(
                "app.services.transformation_engine.transformation_engine.TransformationEngine.apply_transformation",
                side_effect=SECRET,
            ):
                r = await async_authorized_client.post(
                    f"{self.BASE}/apply-fix",
                    json={"dataset_id": str(ds.id), "issue_id": issue_id, "preview_mode": False},
                )
        body = r.json()
        assert r.status_code == 200 and body["success"] is False, body
        assert "secret-bucket" not in r.text and "boom" not in r.text

    def test_fix_engine_preview_does_not_echo_either(self):
        """One layer down: the route copies the engine's error string into the body."""
        from app.models.transformation import TransformationType
        from app.services.fix_suggestion_engine import FixSuggestionEngine

        engine = FixSuggestionEngine()
        fix = MagicMock(transformation_type=list(TransformationType)[0].value, parameters={})
        with patch.object(engine.transformation_engine, "preview_transformation", side_effect=SECRET):
            result = engine.preview_fix(pd.DataFrame({"a": [1]}), MagicMock(), fix)
        assert result["success"] is False
        assert "secret-bucket" not in result["error"] and "boom" not in result["error"]

    def test_transformation_engine_catch_all_does_not_echo(self):
        from app.models.transformation import TransformationType
        from app.services.transformation_engine.transformation_engine import (
            TransformationEngine,
        )

        engine = TransformationEngine()
        with patch.object(engine, "create_transformation", side_effect=SECRET):
            result = engine.apply_transformation(
                df=pd.DataFrame({"a": [" x "]}), transformation_type=list(TransformationType)[0], parameters={}
            )
        assert result.success is False
        assert "secret-bucket" not in (result.error or "") and "boom" not in (result.error or "")


class TestTransformations:
    BASE = "/api/v1/transformations"

    def _dataset(self):
        ds = MagicMock(spec=DatasetMetadata)
        ds.id = ObjectId()
        ds.dataset_id = str(ObjectId())
        ds.user_id = TEST_USER
        ds.file_path = ds.s3_url = "https://test-bucket.s3.amazonaws.com/f.parquet"
        ds.num_rows = 3
        ds.num_columns = 1
        ds.columns = ["a"]
        ds.update_timestamp = MagicMock()
        ds.save = AsyncMock()
        return ds

    @pytest.mark.parametrize("path,body", [
        ("preview", {"transformation_steps": [{"transformation_type": "trim_whitespace", "parameters": {}}]}),
        ("apply", {"transformation_type": "trim_whitespace", "parameters": {}}),
        ("pipeline/apply", {"transformations": [{"type": "trim_whitespace", "parameters": {}}]}),
        ("auto-clean", {}),
    ])
    async def test_success_false_bodies(self, async_authorized_client, setup_database, path, body):
        ds = self._dataset()
        with patch("app.models.dataset.DatasetMetadata.find_one", new_callable=AsyncMock, return_value=ds), \
             patch("app.models.user_data.UserData.find_one", new_callable=AsyncMock, return_value=ds), \
             patch("app.services.s3_service.download_file_from_s3", side_effect=SECRET), \
             patch("app.api.routes.transformations.get_dataframe_from_s3", new_callable=AsyncMock, side_effect=SECRET, create=True):
            r = await async_authorized_client.post(f"{self.BASE}/{path}", json={"dataset_id": ds.dataset_id, **body})
        data = r.json()
        assert data["success"] is False, data
        _assert_sanitized(r, data["error"])

    async def test_bulk_preview(self, async_authorized_client, setup_database):
        ds = self._dataset()
        with patch("app.models.dataset.DatasetMetadata.find_one", new_callable=AsyncMock, return_value=ds), \
             patch("app.models.user_data.UserData.find_one", new_callable=AsyncMock, return_value=ds), \
             patch("app.services.s3_service.download_file_from_s3", side_effect=SECRET):
            r = await async_authorized_client.post(
                f"{self.BASE}/datasets/{ds.dataset_id}/bulk-preview",
                json={"selected_columns": ["a"], "transformation_type": "trim_whitespace"},
            )
        data = r.json()
        assert data["success"] is False, data
        # The service wraps the failure in a fixed-message OperationError, so the
        # domain branch answers here; no reference, but nothing leaks either.
        assert r.status_code == 200
        assert "secret-bucket" not in r.text and "boom" not in r.text

    async def test_validate_errors_list(self, async_authorized_client, setup_database):
        ds = self._dataset()
        with patch("app.models.dataset.DatasetMetadata.find_one", new_callable=AsyncMock, return_value=ds), \
             patch("app.models.user_data.UserData.find_one", new_callable=AsyncMock, return_value=ds), \
             patch("app.services.s3_service.download_file_from_s3", side_effect=SECRET), \
             patch("app.api.routes.transformations.get_dataframe_from_s3", new_callable=AsyncMock, side_effect=SECRET, create=True):
            r = await async_authorized_client.post(
                f"{self.BASE}/validate",
                json={"dataset_id": ds.dataset_id, "transformations": [{"type": "trim_whitespace", "parameters": {}}]},
            )
        data = r.json()
        assert data["is_valid"] is False, data
        _assert_sanitized(r, " ".join(data["errors"]))
