"""
Tests for data processing API endpoints
"""

import pytest
from httpx import AsyncClient
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pandas as pd
import io
from datetime import datetime, timezone
from bson import ObjectId

from app.main import app
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
    mock_data.s3_url = "s3://test-bucket/test-file-123.csv"  # Add for backward compatibility
    mock_data.num_rows = 100
    mock_data.num_columns = 5
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
    mock_data.data_schema = []  # Changed from file_type "csv"
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
                        assert "columns" in data["statistics"]
                        
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
            assert "Dataset not found" in response.json()["detail"]
    
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
            assert data == schema_data
    
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
        
        mock_user_data = create_mock_user_data(schema=schema_data, is_processed=True)
        
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            
            
            response = await async_authorized_client.get("/api/v1/data/test-file-123/statistics")

            assert response.status_code == 200

            data = response.json()

            assert "columns" in data
            assert "age" in data["columns"]
            assert "salary" in data["columns"]
    
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
        
        mock_user_data = create_mock_user_data(schema=schema_data, is_processed=True)
        
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            
            
            response = await async_authorized_client.get("/api/v1/data/test-file-123/quality")

            assert response.status_code == 200

            data = response.json()

            assert data["overall_quality_score"] == 0.95
            assert "dimension_scores" in data
            assert len(data["recommendations"]) == 1
    
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
                
                response = await async_authorized_client.get("/api/v1/data/test-file-123/preview?limit=3")
        
                assert response.status_code == 200
                data = response.json()
                assert "data" in data
                assert len(data["data"]) == 3
                assert "total_rows" in data
                assert data["total_rows"] == 5
    
    @pytest.mark.asyncio
    async def test_export_data_csv(self, async_authorized_client, setup_database, sample_dataframe):
        """Test exporting data as CSV"""
        mock_user_data = create_mock_user_data(is_processed=True)
        
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_user_data
            
            with patch('app.services.s3_service.s3_service.download_file_bytes', new_callable=AsyncMock) as mock_s3_download:
                # Mock S3 file retrieval
                csv_buffer = io.BytesIO()

                sample_dataframe.to_csv(csv_buffer, index=False)

                csv_bytes = csv_buffer.getvalue()

                mock_s3_download.return_value = csv_bytes
                
                with patch('app.utils.s3.upload_file_to_s3') as mock_upload:
                    mock_upload.return_value = (True, "https://test-bucket.s3.amazonaws.com/exports/test.csv")
                    
                    response = await async_authorized_client.post(
            "/api/v1/data/test-file-123/export",
            json={"format": "csv"}
        )
        
                    assert response.status_code == 200
                    data = response.json()
                    assert "download_url" in data
                    assert "exports/test" in data["download_url"]
    
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