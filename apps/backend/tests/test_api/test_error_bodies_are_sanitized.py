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

pytestmark = pytest.mark.asyncio

TEST_USER = "test_user_123"
SECRET = RuntimeError("s3://secret-bucket/datasets/u1/k.parquet: boom from the driver")


def _assert_sanitized(response, error_text: str):
    assert response.status_code == 200, response.text
    assert "secret-bucket" not in response.text
    assert "boom" not in response.text
    assert response.headers["X-Request-ID"] in error_text
    assert "internal error" in error_text


class TestTransformationEngine:
    @pytest.mark.parametrize("method", ["apply_transformation", "preview_transformation"])
    def test_transformation_engine_catch_alls_do_not_echo(self, method):
        """Both the validation catch-all (create_transformation raises inside
        validate_transformation) and the apply/preview catch-all (validation passes,
        then the transformation blows up) used to return str(e) as result.error."""
        from app.models.transformation import TransformationType
        from app.services.transformation_engine.transformation_engine import (
            TransformationEngine,
            TransformationResult,
        )

        engine = TransformationEngine()
        ttype = list(TransformationType)[0]
        df = pd.DataFrame({"a": [" x "]})
        with patch.object(engine, "create_transformation", side_effect=SECRET):
            via_validation = getattr(engine, method)(df=df, transformation_type=ttype, parameters={})
        with patch.object(engine, "validate_transformation", return_value=TransformationResult(success=True)), \
             patch.object(engine, "create_transformation", side_effect=SECRET):
            via_catch_all = getattr(engine, method)(df=df, transformation_type=ttype, parameters={})
        for result in (via_validation, via_catch_all):
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

    async def test_lookup_failure_hits_the_handlers_own_generic_branch(self, async_authorized_client, setup_database):
        """auto-clean delegates the work (and its failures) to code that already answers
        success:false; its own generic branch is reached when the dataset lookup itself
        blows up."""
        ds = self._dataset()
        with patch("app.models.dataset.DatasetMetadata.find_one", new_callable=AsyncMock, side_effect=SECRET), \
             patch("app.models.user_data.UserData.find_one", new_callable=AsyncMock, side_effect=SECRET):
            r = await async_authorized_client.post(
                f"{self.BASE}/auto-clean", json={"dataset_id": ds.dataset_id}
            )
        data = r.json()
        assert data["success"] is False, data
        _assert_sanitized(r, data["error"])

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
