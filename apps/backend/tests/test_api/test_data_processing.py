"""
Tests for data processing API endpoints.

Every test here runs against a **real** `UserData` document in the test database.
The previous version patched `UserData.find_one` to return a MagicMock, which made the
query itself untested by construction — six of these endpoints compared the string path
id against an ObjectId `_id` and answered a permanent 404 in production while this file
stayed green (#465). Only S3 is stubbed now.
"""

import io
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from bson import ObjectId

from app.models.user_data import UserData

TEST_USER = "test_user_123"  # what async_authorized_client authenticates as


async def seed_user_data(**overrides) -> UserData:
    """Insert a real UserData for the authenticated test user, with sensible defaults."""
    fields = dict(
        user_id=TEST_USER,
        filename="test_data.csv",
        original_filename="test_data.csv",
        s3_url="https://test-bucket.s3.amazonaws.com/datasets/test_user_123/test-file-123.csv",
        num_rows=100,
        num_columns=5,
        file_type="csv",  # Required for data processor
        data_schema=[],
        is_processed=False,
        schema=None,
        statistics=None,
        quality_report=None,
    )
    fields.update(overrides)
    doc = UserData(**fields)
    await doc.insert()
    return doc


@pytest.fixture
def sample_dataframe():
    """Sample dataframe for testing"""
    return pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'age': [25, 30, 35, 40, 45],
        'salary': [50000, 60000, 70000, 80000, 90000],
        'email': ['alice@example.com', 'bob@example.com', 'charlie@example.com', 'david@example.com', 'eve@example.com'],
        'join_date': pd.to_datetime(['2020-01-01', '2020-02-01', '2020-03-01', '2020-04-01', '2020-05-01'])
    })


def _csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()


class TestDataProcessingAPI:
    """Test suite for data processing endpoints"""

    @pytest.mark.asyncio
    async def test_process_dataset_success(self, async_authorized_client, setup_database, sample_dataframe):
        """Test successful dataset processing"""
        user_data = await seed_user_data()

        with patch('app.services.s3_service.s3_service.bucket_name', 'test-bucket'), \
             patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock, return_value=_csv(sample_dataframe)):
            response = await async_authorized_client.post(
                "/api/v1/data/process",
                json={"file_id": str(user_data.id)}
            )

        assert response.status_code == 200
        data = response.json()

        # Check schema
        assert "schema" in data
        assert data["schema"]["row_count"] == 5
        assert data["schema"]["column_count"] == 6
        assert len(data["schema"]["columns"]) == 6

        # Check statistics
        assert "statistics" in data
        assert "column_statistics" in data["statistics"]

        # Check quality report
        assert "quality_report" in data
        assert "overall_quality_score" in data["quality_report"]
        assert 0 <= data["quality_report"]["overall_quality_score"] <= 1

        # The real document was updated, not a mock's `save`
        stored = await UserData.get(user_data.id)
        assert stored is not None and stored.is_processed is True

    @pytest.mark.asyncio
    async def test_process_dataset_not_found(self, async_authorized_client, setup_database):
        """Test processing non-existent dataset"""
        response = await async_authorized_client.post(
            "/api/v1/data/process",
            json={"file_id": str(ObjectId())}
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_schema_success(self, async_authorized_client, setup_database):
        """Test getting dataset schema"""
        schema_data = {
            "row_count": 5,
            "column_count": 6,
            "columns": [
                {"name": "id", "type": "integer", "nullable": False},
                {"name": "name", "type": "string", "nullable": False},
                {"name": "age", "type": "integer", "nullable": False},
                {"name": "salary", "type": "float", "nullable": False},
                {"name": "email", "type": "email", "nullable": False},
                {"name": "join_date", "type": "datetime", "nullable": False}
            ]
        }
        user_data = await seed_user_data(schema=schema_data, is_processed=True)

        response = await async_authorized_client.get(f"/api/v1/data/{user_data.id}/schema")

        assert response.status_code == 200
        data = response.json()
        assert "schema" in data
        assert data["schema"] == schema_data

    @pytest.mark.asyncio
    async def test_get_statistics_success(self, async_authorized_client, setup_database):
        """Test getting dataset statistics"""
        stats_data = {
            "columns": {
                "age": {
                    "mean": 35.0, "median": 35.0, "std": 7.07, "min": 25.0, "max": 45.0,
                    "missing_count": 0, "missing_percentage": 0.0
                },
                "salary": {
                    "mean": 70000.0, "median": 70000.0, "std": 14142.14, "min": 50000.0, "max": 90000.0,
                    "missing_count": 0, "missing_percentage": 0.0
                }
            }
        }
        user_data = await seed_user_data(statistics=stats_data, is_processed=True)

        response = await async_authorized_client.get(f"/api/v1/data/{user_data.id}/statistics")

        assert response.status_code == 200
        data = response.json()
        assert "statistics" in data
        assert "columns" in data["statistics"]
        assert "age" in data["statistics"]["columns"]
        assert "salary" in data["statistics"]["columns"]

    @pytest.mark.asyncio
    async def test_get_quality_report_success(self, async_authorized_client, setup_database):
        """Test getting data quality report"""
        quality_data = {
            "overall_quality_score": 0.95,
            "dimension_scores": {
                "completeness": 1.0, "consistency": 0.9, "validity": 0.95, "uniqueness": 0.9
            },
            "issues": [],
            "recommendations": ["Consider adding data validation rules"]
        }
        user_data = await seed_user_data(quality_report=quality_data, is_processed=True)

        response = await async_authorized_client.get(f"/api/v1/data/{user_data.id}/quality")

        assert response.status_code == 200
        data = response.json()
        assert "quality_report" in data
        assert data["quality_report"]["overall_quality_score"] == 0.95
        assert "dimension_scores" in data["quality_report"]
        assert len(data["quality_report"]["recommendations"]) == 1

    @pytest.mark.asyncio
    async def test_quality_report_consolidated_full(self, async_authorized_client, setup_database):
        """Consolidated report exposes 0-100 score, components, gates (issue #102)."""
        quality_data = {
            "overall_quality_score": 0.86,
            "score_0_100": 86.0,
            "dimension_scores": {"completeness": 0.9, "validity": 0.8},
            "component_scores": {
                "completeness": 90.0, "validity": 80.0, "consistency": 95.0,
                "uniqueness": 100.0, "accuracy": 80.0,
            },
            "recommendations": ["Fix missing values"],
            "actionable_recommendations": [{
                "dimension": "completeness", "description": "Apply 'fill_missing' to age",
                "transformation_type": "fill_missing", "affected_columns": ["age"],
                "severity": "high",
            }],
            "critical_issues": [{"x": 1}],
            "warnings": [],
        }
        user_data = await seed_user_data(quality_report=quality_data, is_processed=True)

        response = await async_authorized_client.get(f"/api/v1/data/{user_data.id}/quality-report")

        assert response.status_code == 200
        data = response.json()
        assert data["score_0_100"] == 86.0
        assert data["partial"] is False
        assert data["component_scores"]["completeness"] == 90.0
        assert data["actionable_recommendations"][0]["transformation_type"] == "fill_missing"
        assert len(data["gates"]) >= 1
        assert data["gates"][0]["is_blocking"] is False
        assert data["gates"][0]["passed"] is True
        assert data["critical_issue_count"] == 1

    @pytest.mark.asyncio
    async def test_quality_report_consolidated_partial_pre_102(self, async_authorized_client, setup_database):
        """Pre-#102 cached report (no score_0_100) degrades to partial, never 500."""
        quality_data = {
            "overall_quality_score": 0.6,
            "dimension_scores": {
                "completeness": 0.5, "validity": 0.7, "consistency": 0.9,
                "uniqueness": 1.0, "accuracy": 0.7,
            },
            "recommendations": [],
        }
        user_data = await seed_user_data(quality_report=quality_data, is_processed=True)

        response = await async_authorized_client.get(f"/api/v1/data/{user_data.id}/quality-report")

        assert response.status_code == 200
        data = response.json()
        assert data["partial"] is True
        assert data["score_0_100"] > 0  # derived from legacy 0-1 dimension scores
        # completeness 50 < 80 threshold -> gate fails
        assert data["gates"][0]["passed"] is False
        assert "completeness" in data["gates"][0]["failing_dimensions"]

    @pytest.mark.asyncio
    async def test_get_data_preview_success(self, async_authorized_client, setup_database, sample_dataframe):
        """Test getting data preview"""
        user_data = await seed_user_data(is_processed=True)

        with patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock, return_value=_csv(sample_dataframe)):
            response = await async_authorized_client.get(f"/api/v1/data/{user_data.id}/preview?rows=3")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 3
        assert "total_rows" in data
        assert data["total_rows"] == 5

    @pytest.mark.parametrize("fmt", ["csv", "excel", "json", "parquet"])
    @pytest.mark.asyncio
    async def test_export_data_produces_working_download_url(
        self, async_authorized_client, setup_database, sample_dataframe, fmt
    ):
        """Export uploads a real artifact and returns a working (presigned) URL."""
        user_data = await seed_user_data(is_processed=True)
        presigned = "https://test-bucket.s3.amazonaws.com/exports/x?X-Amz-Signature=abc"

        with patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock, return_value=_csv(sample_dataframe)), \
             patch('app.services.s3_service.s3_service.upload_file_obj',
                   new_callable=AsyncMock) as mock_upload, \
             patch('app.services.s3_service.s3_service.generate_presigned_url',
                   return_value=presigned) as mock_presign:
            response = await async_authorized_client.post(
                f"/api/v1/data/{user_data.id}/export?format={fmt}"
            )

        assert response.status_code == 200
        data = response.json()
        # The artifact was actually uploaded, and the returned URL is the presigned one
        assert mock_upload.await_count == 1
        uploaded_key = mock_upload.await_args.args[1]
        assert uploaded_key.startswith("exports/")
        assert uploaded_key.endswith(f"_processed.{fmt}")
        assert data["download_url"] == presigned
        assert "/download?format=" not in data["download_url"]  # regression: dead route gone
        assert data["export_format"] == fmt
        # presign is asked for a clean download filename via Content-Disposition
        mock_presign.assert_called_once_with(uploaded_key, filename=data["export_filename"])

    @pytest.mark.asyncio
    async def test_export_sanitizes_traversal_filename(
        self, async_authorized_client, setup_database, sample_dataframe
    ):
        """A path-traversal original_filename cannot escape the exports/ prefix."""
        user_data = await seed_user_data(is_processed=True, original_filename="../../admin/secret.csv")

        with patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock, return_value=_csv(sample_dataframe)), \
             patch('app.services.s3_service.s3_service.upload_file_obj',
                   new_callable=AsyncMock) as mock_upload, \
             patch('app.services.s3_service.s3_service.generate_presigned_url',
                   return_value="https://x"):
            response = await async_authorized_client.post(
                f"/api/v1/data/{user_data.id}/export?format=csv"
            )

        assert response.status_code == 200
        uploaded_key = mock_upload.await_args.args[1]
        # structural: escaped the traversal and lands under the user/file prefix
        assert ".." not in uploaded_key
        assert uploaded_key.startswith("exports/")
        assert uploaded_key.endswith("/secret_processed.csv")

    @pytest.mark.asyncio
    async def test_export_filename_is_header_safe(
        self, async_authorized_client, setup_database, sample_dataframe
    ):
        """Quote/semicolon in the name can't inject the Content-Disposition header."""
        user_data = await seed_user_data(is_processed=True, original_filename='evil";name.csv')

        with patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock, return_value=_csv(sample_dataframe)), \
             patch('app.services.s3_service.s3_service.upload_file_obj',
                   new_callable=AsyncMock), \
             patch('app.services.s3_service.s3_service.generate_presigned_url',
                   return_value="https://x") as mock_presign:
            response = await async_authorized_client.post(
                f"/api/v1/data/{user_data.id}/export?format=csv"
            )

        assert response.status_code == 200
        download_name = mock_presign.call_args.kwargs["filename"]
        assert '"' not in download_name and ';' not in download_name

    @pytest.mark.asyncio
    async def test_export_unknown_source_type_returns_422(
        self, async_authorized_client, setup_database
    ):
        """An unreadable source type is an honest 422, not a 500 or false success."""
        user_data = await seed_user_data(is_processed=True, original_filename="data.bin", file_type="bin")

        with patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock, return_value=b"\x00\x01"):
            response = await async_authorized_client.post(
                f"/api/v1/data/{user_data.id}/export?format=csv"
            )

        assert response.status_code == 422

    @pytest.mark.parametrize("source", ["excel", "parquet"])
    @pytest.mark.asyncio
    async def test_export_reads_binary_sources(
        self, async_authorized_client, setup_database, sample_dataframe, source
    ):
        """Excel and Parquet source files are read, not just CSV."""
        user_data = await seed_user_data(
            is_processed=True,
            original_filename=f"data.{'xlsx' if source == 'excel' else 'parquet'}",
            file_type="xlsx" if source == "excel" else "parquet",
        )
        buf = io.BytesIO()
        if source == "excel":
            sample_dataframe.to_excel(buf, index=False)
        else:
            sample_dataframe.to_parquet(buf, index=False)

        with patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock, return_value=buf.getvalue()), \
             patch('app.services.s3_service.s3_service.upload_file_obj',
                   new_callable=AsyncMock), \
             patch('app.services.s3_service.s3_service.generate_presigned_url',
                   return_value="https://x"):
            response = await async_authorized_client.post(
                f"/api/v1/data/{user_data.id}/export?format=csv"
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_reads_json_source(
        self, async_authorized_client, setup_database, sample_dataframe
    ):
        """A JSON-typed source is readable, not a 422."""
        user_data = await seed_user_data(is_processed=True, original_filename="data.json", file_type="json")

        with patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock,
                   return_value=sample_dataframe.to_json(orient="records").encode()), \
             patch('app.services.s3_service.s3_service.upload_file_obj',
                   new_callable=AsyncMock), \
             patch('app.services.s3_service.s3_service.generate_presigned_url',
                   return_value="https://x"):
            response = await async_authorized_client.post(
                f"/api/v1/data/{user_data.id}/export?format=csv"
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_rejects_oversized_source(
        self, async_authorized_client, setup_database
    ):
        """A source larger than MAX_EXPORT_SOURCE_BYTES is rejected with 413."""
        from app.api.routes.data_processing import MAX_EXPORT_SOURCE_BYTES

        user_data = await seed_user_data(is_processed=True)

        with patch('app.services.s3_service.s3_service.get_file_size',
                   new_callable=AsyncMock, return_value=MAX_EXPORT_SOURCE_BYTES + 1), \
             patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock) as mock_download:
            response = await async_authorized_client.post(
                f"/api/v1/data/{user_data.id}/export?format=csv"
            )

        assert response.status_code == 413
        mock_download.assert_not_awaited()  # never downloaded the oversized file

    @pytest.mark.asyncio
    async def test_export_data_fails_loudly_on_s3_error(
        self, async_authorized_client, setup_database
    ):
        """A storage failure returns an error, never a false 'export_ready'."""
        user_data = await seed_user_data(is_processed=True)

        with patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock, side_effect=RuntimeError("s3 down")):
            response = await async_authorized_client.post(
                f"/api/v1/data/{user_data.id}/export?format=csv"
            )

        assert response.status_code == 500
        assert "export_ready" not in response.text

    @pytest.mark.asyncio
    async def test_process_dataset_with_invalid_file(self, async_authorized_client, setup_database):
        """Test processing dataset with invalid file"""
        user_data = await seed_user_data(is_processed=True)

        with patch('app.services.s3_service.s3_service.download_file_bytes',
                   new_callable=AsyncMock, side_effect=Exception("Failed to retrieve file")):
            response = await async_authorized_client.post(
                "/api/v1/data/process",
                json={"file_id": str(user_data.id)}
            )

        assert response.status_code == 500
        # Generic body, no internal detail leaked (issue #269).
        body = response.json()
        assert body["detail"] == "Internal server error"
        assert body.get("request_id")
        assert "Failed to retrieve file" not in response.text
