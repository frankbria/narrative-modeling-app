"""
Tests for data processing API endpoints
"""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from bson import ObjectId

from app.models.user_data import UserData


def create_mock_user_data(**kwargs):
    """Helper to create mock user data with defaults"""
    mock_data = MagicMock(spec=UserData)

    # Set default attributes
    mock_data.id = ObjectId()
    mock_data.user_id = "test-user-123"
    mock_data.filename = "test_data.csv"
    mock_data.original_filename = "test_data.csv"
    mock_data.s3_url = "s3://test-bucket/test-file-123.csv"
    mock_data.num_rows = 100
    mock_data.num_columns = 5
    mock_data.file_type = "csv"  # Required for data processor
    mock_data.data_schema = [
        {
            "field_name": "id",
            "field_type": "numeric",
            "inferred_dtype": "int64",
            "unique_values": 100,
            "missing_values": 0,
            "example_values": [1, 2, 3],
            "is_constant": False,
            "is_high_cardinality": True
        }
    ]
    mock_data.is_processed = False
    mock_data.schema = None
    mock_data.statistics = None
    mock_data.quality_report = None
    mock_data.save = AsyncMock()

    # Update with any provided kwargs
    for key, value in kwargs.items():
        setattr(mock_data, key, value)

    return mock_data


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


class TestDataProcessingAPI:
    """Test suite for data processing endpoints"""
    
    @pytest.mark.asyncio
    async def test_process_dataset_success(self, async_authorized_client, setup_database, sample_dataframe):
        """Test successful dataset processing"""
        mock_user_data = create_mock_user_data()
        
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            
            with patch('app.services.s3_service.s3_service.bucket_name', 'test-bucket'):
                with patch('app.services.s3_service.s3_service.download_file_bytes', new_callable=AsyncMock) as mock_s3_download:
                    # Mock S3 file retrieval
                    csv_buffer = io.BytesIO()
                    sample_dataframe.to_csv(csv_buffer, index=False)
                    csv_bytes = csv_buffer.getvalue()
                    mock_s3_download.return_value = csv_bytes
                    
                    with patch.object(mock_user_data, 'save', new_callable=AsyncMock):
                        response = await async_authorized_client.post(
            "/api/v1/data/process",
            json={"file_id": "test-file-123"}
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
    
    @pytest.mark.asyncio
    async def test_process_dataset_not_found(self, async_authorized_client, setup_database):
        """Test processing non-existent dataset"""
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None
            
            response = await async_authorized_client.post(
                    "/api/v1/data/process",
                json={"file_id": "non-existent-123"}
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
        
        mock_user_data = create_mock_user_data(schema=schema_data, is_processed=True)
        
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            
            
            response = await async_authorized_client.get("/api/v1/data/test-file-123/schema")

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
                    "mean": 35.0,
                    "median": 35.0,
                    "std": 7.07,
                    "min": 25.0,
                    "max": 45.0,
                    "missing_count": 0,
                    "missing_percentage": 0.0
                },
                "salary": {
                    "mean": 70000.0,
                    "median": 70000.0,
                    "std": 14142.14,
                    "min": 50000.0,
                    "max": 90000.0,
                    "missing_count": 0,
                    "missing_percentage": 0.0
                }
            }
        }
        
        mock_user_data = create_mock_user_data(statistics=stats_data, is_processed=True)

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data


            response = await async_authorized_client.get("/api/v1/data/test-file-123/statistics")

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
                "completeness": 1.0,
                "consistency": 0.9,
                "validity": 0.95,
                "uniqueness": 0.9
            },
            "issues": [],
            "recommendations": ["Consider adding data validation rules"]
        }
        
        mock_user_data = create_mock_user_data(quality_report=quality_data, is_processed=True)

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data


            response = await async_authorized_client.get("/api/v1/data/test-file-123/quality")

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
        mock_user_data = create_mock_user_data(quality_report=quality_data, is_processed=True)
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            response = await async_authorized_client.get("/api/v1/data/test-file-123/quality-report")

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
        mock_user_data = create_mock_user_data(quality_report=quality_data, is_processed=True)
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            response = await async_authorized_client.get("/api/v1/data/test-file-123/quality-report")

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
        mock_user_data = create_mock_user_data(is_processed=True)
        
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            
            with patch('app.services.s3_service.s3_service.download_file_bytes', new_callable=AsyncMock) as mock_s3_download:
                # Mock S3 file retrieval
                csv_buffer = io.BytesIO()
                sample_dataframe.to_csv(csv_buffer, index=False)
                csv_bytes = csv_buffer.getvalue()
                mock_s3_download.return_value = csv_bytes
                
                response = await async_authorized_client.get("/api/v1/data/test-file-123/preview?rows=3")
        
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
        mock_user_data = create_mock_user_data(is_processed=True)

        csv_bytes = sample_dataframe.to_csv(index=False).encode()
        presigned = "https://test-bucket.s3.amazonaws.com/exports/x?X-Amz-Signature=abc"

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            with patch('app.services.s3_service.s3_service.download_file_bytes',
                       new_callable=AsyncMock, return_value=csv_bytes), \
                 patch('app.services.s3_service.s3_service.upload_file_obj',
                       new_callable=AsyncMock) as mock_upload, \
                 patch('app.services.s3_service.s3_service.generate_presigned_url',
                       return_value=presigned) as mock_presign:
                response = await async_authorized_client.post(
                    f"/api/v1/data/test-file-123/export?format={fmt}"
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
        mock_user_data = create_mock_user_data(
            is_processed=True, original_filename="../../admin/secret.csv"
        )
        csv_bytes = sample_dataframe.to_csv(index=False).encode()

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            with patch('app.services.s3_service.s3_service.download_file_bytes',
                       new_callable=AsyncMock, return_value=csv_bytes), \
                 patch('app.services.s3_service.s3_service.upload_file_obj',
                       new_callable=AsyncMock) as mock_upload, \
                 patch('app.services.s3_service.s3_service.generate_presigned_url',
                       return_value="https://x"):
                response = await async_authorized_client.post(
                    "/api/v1/data/test-file-123/export?format=csv"
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
        mock_user_data = create_mock_user_data(
            is_processed=True, original_filename='evil";name.csv'
        )
        csv_bytes = sample_dataframe.to_csv(index=False).encode()

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            with patch('app.services.s3_service.s3_service.download_file_bytes',
                       new_callable=AsyncMock, return_value=csv_bytes), \
                 patch('app.services.s3_service.s3_service.upload_file_obj',
                       new_callable=AsyncMock), \
                 patch('app.services.s3_service.s3_service.generate_presigned_url',
                       return_value="https://x") as mock_presign:
                response = await async_authorized_client.post(
                    "/api/v1/data/test-file-123/export?format=csv"
                )

        assert response.status_code == 200
        download_name = mock_presign.call_args.kwargs["filename"]
        assert '"' not in download_name and ';' not in download_name

    @pytest.mark.asyncio
    async def test_export_unknown_source_type_returns_422(
        self, async_authorized_client, setup_database
    ):
        """An unreadable source type is an honest 422, not a 500 or false success."""
        mock_user_data = create_mock_user_data(
            is_processed=True, original_filename="data.bin", file_type="bin"
        )

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            with patch('app.services.s3_service.s3_service.download_file_bytes',
                       new_callable=AsyncMock, return_value=b"\x00\x01"):
                response = await async_authorized_client.post(
                    "/api/v1/data/test-file-123/export?format=csv"
                )

        assert response.status_code == 422

    @pytest.mark.parametrize("source", ["excel", "parquet"])
    @pytest.mark.asyncio
    async def test_export_reads_binary_sources(
        self, async_authorized_client, setup_database, sample_dataframe, source
    ):
        """Excel and Parquet source files are read, not just CSV."""
        mock_user_data = create_mock_user_data(
            is_processed=True,
            original_filename=f"data.{'xlsx' if source == 'excel' else 'parquet'}",
            file_type="xlsx" if source == "excel" else "parquet",
        )
        buf = io.BytesIO()
        if source == "excel":
            sample_dataframe.to_excel(buf, index=False)
        else:
            sample_dataframe.to_parquet(buf, index=False)
        src_bytes = buf.getvalue()

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            with patch('app.services.s3_service.s3_service.download_file_bytes',
                       new_callable=AsyncMock, return_value=src_bytes), \
                 patch('app.services.s3_service.s3_service.upload_file_obj',
                       new_callable=AsyncMock), \
                 patch('app.services.s3_service.s3_service.generate_presigned_url',
                       return_value="https://x"):
                response = await async_authorized_client.post(
                    "/api/v1/data/test-file-123/export?format=csv"
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_reads_json_source(
        self, async_authorized_client, setup_database, sample_dataframe
    ):
        """A JSON-typed source is readable, not a 422."""
        mock_user_data = create_mock_user_data(
            is_processed=True, original_filename="data.json", file_type="json"
        )
        json_bytes = sample_dataframe.to_json(orient="records").encode()

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            with patch('app.services.s3_service.s3_service.download_file_bytes',
                       new_callable=AsyncMock, return_value=json_bytes), \
                 patch('app.services.s3_service.s3_service.upload_file_obj',
                       new_callable=AsyncMock), \
                 patch('app.services.s3_service.s3_service.generate_presigned_url',
                       return_value="https://x"):
                response = await async_authorized_client.post(
                    "/api/v1/data/test-file-123/export?format=csv"
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_export_rejects_oversized_source(
        self, async_authorized_client, setup_database
    ):
        """A source larger than MAX_EXPORT_SOURCE_BYTES is rejected with 413."""
        from app.api.routes.data_processing import MAX_EXPORT_SOURCE_BYTES

        mock_user_data = create_mock_user_data(is_processed=True)

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            with patch('app.services.s3_service.s3_service.get_file_size',
                       new_callable=AsyncMock, return_value=MAX_EXPORT_SOURCE_BYTES + 1), \
                 patch('app.services.s3_service.s3_service.download_file_bytes',
                       new_callable=AsyncMock) as mock_download:
                response = await async_authorized_client.post(
                    "/api/v1/data/test-file-123/export?format=csv"
                )

        assert response.status_code == 413
        mock_download.assert_not_awaited()  # never downloaded the oversized file

    @pytest.mark.asyncio
    async def test_export_data_fails_loudly_on_s3_error(
        self, async_authorized_client, setup_database
    ):
        """A storage failure returns an error, never a false 'export_ready'."""
        mock_user_data = create_mock_user_data(is_processed=True)

        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            with patch('app.services.s3_service.s3_service.download_file_bytes',
                       new_callable=AsyncMock, side_effect=RuntimeError("s3 down")):
                response = await async_authorized_client.post(
                    "/api/v1/data/test-file-123/export?format=csv"
                )

        assert response.status_code == 500
        assert "export_ready" not in response.text
    
    @pytest.mark.asyncio
    async def test_process_dataset_with_invalid_file(self, async_authorized_client, setup_database):
        """Test processing dataset with invalid file"""
        mock_user_data = create_mock_user_data(is_processed=True)
        
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            
            with patch('app.services.s3_service.s3_service.download_file_bytes', new_callable=AsyncMock) as mock_s3_download:
                # Mock S3 file retrieval failure
                mock_s3_download.side_effect = Exception("Failed to retrieve file")
                
                response = await async_authorized_client.post(
                    "/api/v1/data/process",
                    json={"file_id": "test-file-123"}
                )
                
                assert response.status_code == 500
                assert "Error processing dataset" in response.json()["detail"]