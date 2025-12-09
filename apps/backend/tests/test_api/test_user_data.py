"""
Test suite for User Data API endpoints.

Integration tests for user_data routes covering all endpoints:
- POST / - Create user data
- GET / - List all user data for user
- GET /latest - Get most recent user data
- GET /{id} - Get specific user data by ID
- GET /preview - Get preview data with S3 file content
- PUT /{id} - Update user data
- DELETE /{id} - Delete user data
- GET /{id}/ai-summary - Get AI summary
- GET /{id}/eda-summary - Get EDA summary
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone
import uuid
from typing import Dict, Any
from unittest.mock import patch, AsyncMock, MagicMock
from beanie import PydanticObjectId

from app.models.user_data import UserData, AISummary, SchemaField


@pytest.mark.integration
class TestUserDataAPI:
    """Test suite for user data API endpoints."""

    @pytest.fixture
    async def sample_user_data(self, setup_database, mock_user_id: str) -> UserData:
        """Create sample user data for testing."""
        user_data = UserData(
            user_id=mock_user_id,
            filename="test_dataset.csv",
            original_filename="test_dataset.csv",
            s3_url=f"s3://test-bucket/datasets/{mock_user_id}/test_dataset.csv",
            num_rows=100,
            num_columns=3,
            data_schema=[
                SchemaField(
                    field_name="id",
                    field_type="numeric",
                    data_type="ratio",
                    inferred_dtype="int64",
                    unique_values=100,
                    missing_values=0,
                    example_values=[1, 2, 3],
                    is_constant=False,
                    is_high_cardinality=False
                ),
                SchemaField(
                    field_name="value",
                    field_type="numeric",
                    data_type="ratio",
                    inferred_dtype="float64",
                    unique_values=95,
                    missing_values=5,
                    example_values=[10.5, 20.3, 15.7],
                    is_constant=False,
                    is_high_cardinality=False
                ),
                SchemaField(
                    field_name="category",
                    field_type="categorical",
                    data_type="nominal",
                    inferred_dtype="object",
                    unique_values=3,
                    missing_values=0,
                    example_values=["A", "B", "C"],
                    is_constant=False,
                    is_high_cardinality=False
                ),
            ],
            aiSummary=AISummary(
                overview="Test dataset with 100 rows",
                issues=["5 missing values in 'value' column"],
                relationships=["id is unique identifier"],
                suggestions=["Fill missing values in 'value'"],
                rawMarkdown="# Test Summary\n\nThis is a test dataset."
            )
        )
        await user_data.insert()
        return user_data

    @pytest.mark.asyncio
    async def test_create_user_data(
        self,
        async_authorized_client: AsyncClient,
        setup_database,
        mock_user_id: str
    ):
        """Test creating new user data via POST /user-data/."""
        # Create request payload with all required SchemaField fields
        user_data_dict = {
            "filename": "new_dataset.csv",
            "original_filename": "new_dataset.csv",
            "s3_url": f"s3://test-bucket/datasets/{mock_user_id}/new_dataset.csv",
            "num_rows": 50,
            "num_columns": 2,
            "data_schema": [
                {
                    "field_name": "name",
                    "field_type": "text",
                    "data_type": "nominal",
                    "inferred_dtype": "object",
                    "unique_values": 50,
                    "missing_values": 0,
                    "example_values": ["Alice", "Bob", "Charlie"],
                    "is_constant": False,
                    "is_high_cardinality": False
                }
            ]
        }

        response = await async_authorized_client.post(
            "/api/v1/user_data/",
            json=user_data_dict
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "new_dataset.csv"
        assert data["num_rows"] == 50
        assert data["num_columns"] == 2
        assert "_id" in data
        assert data["user_id"] == mock_user_id

    @pytest.mark.asyncio
    async def test_get_all_user_data(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test listing all user data via GET /user-data/."""
        response = await async_authorized_client.get("/api/v1/user_data/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Verify first item has expected fields
        first_item = data[0]
        assert "filename" in first_item
        assert "num_rows" in first_item
        assert "num_columns" in first_item
        assert "_id" in first_item

    @pytest.mark.asyncio
    async def test_get_all_user_data_empty(
        self,
        async_authorized_client: AsyncClient,
        setup_database
    ):
        """Test listing user data when user has no data."""
        response = await async_authorized_client.get("/api/v1/user_data/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_get_latest_user_data(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test getting most recent user data via GET /user-data/latest."""
        response = await async_authorized_client.get("/api/v1/user_data/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == sample_user_data.filename
        assert data["num_rows"] == sample_user_data.num_rows
        assert "_id" in data

    @pytest.mark.asyncio
    async def test_get_latest_user_data_not_found(
        self,
        async_authorized_client: AsyncClient,
        setup_database
    ):
        """Test getting latest user data when none exists."""
        response = await async_authorized_client.get("/api/v1/user_data/latest")

        assert response.status_code == 404
        assert "No data found for user" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_user_data_by_id(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test getting specific user data by ID via GET /user-data/{id}."""
        user_data_id = str(sample_user_data.id)

        response = await async_authorized_client.get(f"/api/v1/user_data/{user_data_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == sample_user_data.filename
        assert data["num_rows"] == sample_user_data.num_rows
        assert str(data["_id"]) == user_data_id

    @pytest.mark.asyncio
    async def test_get_user_data_by_id_invalid_format(
        self,
        async_authorized_client: AsyncClient
    ):
        """Test getting user data with invalid ID format."""
        response = await async_authorized_client.get("/api/v1/user_data/invalid_id")

        assert response.status_code == 400
        assert "Invalid dataset ID format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_user_data_by_id_not_found(
        self,
        async_authorized_client: AsyncClient
    ):
        """Test getting user data that doesn't exist."""
        fake_id = str(PydanticObjectId())

        response = await async_authorized_client.get(f"/api/v1/user_data/{fake_id}")

        assert response.status_code == 404
        assert "Dataset not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_user_data_access_denied(
        self,
        async_authorized_client: AsyncClient,
        setup_database
    ):
        """Test accessing another user's data returns 403."""
        # Create data for different user
        other_user_data = UserData(
            user_id="other_user_123",
            filename="other_dataset.csv",
            original_filename="other_dataset.csv",
            s3_url="s3://test-bucket/other.csv",
            num_rows=10,
            num_columns=2,
            data_schema=[]
        )
        await other_user_data.insert()

        response = await async_authorized_client.get(
            f"/api/v1/user_data/{str(other_user_data.id)}"
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_user_data(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test updating user data via PUT /user-data/{id}."""
        user_data_id = str(sample_user_data.id)

        # Create updated data - serialize data_schema to dicts
        updated_dict = {
            "filename": "updated_dataset.csv",
            "original_filename": "updated_dataset.csv",
            "s3_url": sample_user_data.s3_url,
            "num_rows": 150,
            "num_columns": 3,
            "data_schema": [field.model_dump() for field in sample_user_data.data_schema]
        }

        response = await async_authorized_client.put(
            f"/api/v1/user_data/{user_data_id}",
            json=updated_dict
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "updated_dataset.csv"
        assert data["num_rows"] == 150

    @pytest.mark.asyncio
    async def test_update_user_data_access_denied(
        self,
        async_authorized_client: AsyncClient,
        setup_database
    ):
        """Test updating another user's data returns 403."""
        # Create data for different user
        other_user_data = UserData(
            user_id="other_user_123",
            filename="other.csv",
            original_filename="other.csv",
            s3_url="s3://test/other.csv",
            num_rows=10,
            num_columns=2,
            data_schema=[]
        )
        await other_user_data.insert()

        updated_dict = {
            "filename": "hacked.csv",
            "original_filename": "hacked.csv",
            "s3_url": "s3://test/hacked.csv",
            "num_rows": 999,
            "num_columns": 2,
            "data_schema": []
        }

        response = await async_authorized_client.put(
            f"/api/v1/user_data/{str(other_user_data.id)}",
            json=updated_dict
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_user_data(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test deleting user data via DELETE /user-data/{id}."""
        user_data_id = str(sample_user_data.id)

        response = await async_authorized_client.delete(
            f"/api/v1/user_data/{user_data_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify data was actually deleted
        deleted_doc = await UserData.get(PydanticObjectId(user_data_id))
        assert deleted_doc is None

    @pytest.mark.asyncio
    async def test_delete_user_data_access_denied(
        self,
        async_authorized_client: AsyncClient,
        setup_database
    ):
        """Test deleting another user's data returns 403."""
        # Create data for different user
        other_user_data = UserData(
            user_id="other_user_123",
            filename="other.csv",
            original_filename="other.csv",
            s3_url="s3://test/other.csv",
            num_rows=10,
            num_columns=2,
            data_schema=[]
        )
        await other_user_data.insert()

        response = await async_authorized_client.delete(
            f"/api/v1/user_data/{str(other_user_data.id)}"
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_ai_summary(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test getting AI summary via GET /user-data/{id}/ai-summary."""
        user_data_id = str(sample_user_data.id)

        response = await async_authorized_client.get(
            f"/api/v1/user_data/{user_data_id}/ai-summary"
        )

        assert response.status_code == 200
        data = response.json()
        assert "rawMarkdown" in data
        assert "contextString" in data
        assert "overview" in data
        assert "issues" in data
        assert "relationships" in data
        assert "suggestions" in data
        assert data["overview"] == sample_user_data.aiSummary.overview

    @pytest.mark.asyncio
    async def test_get_ai_summary_not_found(
        self,
        async_authorized_client: AsyncClient,
        setup_database,
        mock_user_id: str
    ):
        """Test getting AI summary when none exists."""
        # Create user data without AI summary
        user_data = UserData(
            user_id=mock_user_id,
            filename="no_summary.csv",
            original_filename="no_summary.csv",
            s3_url="s3://test/no_summary.csv",
            num_rows=10,
            num_columns=2,
            data_schema=[]
        )
        await user_data.insert()

        response = await async_authorized_client.get(
            f"/api/v1/user_data/{str(user_data.id)}/ai-summary"
        )

        assert response.status_code == 404
        assert "AI summary not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_ai_summary_access_denied(
        self,
        async_authorized_client: AsyncClient,
        setup_database
    ):
        """Test accessing another user's AI summary returns 403."""
        other_user_data = UserData(
            user_id="other_user_123",
            filename="other.csv",
            original_filename="other.csv",
            s3_url="s3://test/other.csv",
            num_rows=10,
            num_columns=2,
            data_schema=[],
            aiSummary=AISummary(
                overview="Secret data",
                issues=[],
                relationships=[],
                suggestions=[],
                rawMarkdown="# Secret"
            )
        )
        await other_user_data.insert()

        response = await async_authorized_client.get(
            f"/api/v1/user_data/{str(other_user_data.id)}/ai-summary"
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_eda_summary(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test generating EDA summary via GET /user-data/{id}/eda-summary."""
        user_data_id = str(sample_user_data.id)

        # Mock the EDA summary generation service
        with patch('app.api.routes.user_data.generate_eda_summary', new_callable=AsyncMock) as mock_eda:
            mock_eda.return_value = "**Data Overview**\n\nThis dataset contains..."

            response = await async_authorized_client.get(
                f"/api/v1/user_data/{user_data_id}/eda-summary"
            )

            assert response.status_code == 200
            data = response.json()
            assert "summary" in data
            assert "dataset_id" in data
            assert "created_at" in data
            assert data["dataset_id"] == user_data_id
            mock_eda.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_eda_summary_access_denied(
        self,
        async_authorized_client: AsyncClient,
        setup_database
    ):
        """Test accessing another user's EDA summary returns 403."""
        other_user_data = UserData(
            user_id="other_user_123",
            filename="other.csv",
            original_filename="other.csv",
            s3_url="s3://test/other.csv",
            num_rows=10,
            num_columns=2,
            data_schema=[]
        )
        await other_user_data.insert()

        response = await async_authorized_client.get(
            f"/api/v1/user_data/{str(other_user_data.id)}/eda-summary"
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_preview_data_with_s3_success(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test getting preview data with successful S3 retrieval."""
        import pandas as pd
        import io

        # Mock S3 client and response
        mock_df = pd.DataFrame({
            "id": [1, 2, 3],
            "value": [10.5, 20.3, 15.7],
            "category": ["A", "B", "C"]
        })
        csv_buffer = io.BytesIO()
        mock_df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        with patch('app.api.routes.user_data.boto3.client') as mock_boto:
            mock_s3_client = MagicMock()
            mock_s3_client.get_object.return_value = {
                "Body": MagicMock(read=MagicMock(return_value=csv_content))
            }
            mock_boto.return_value = mock_s3_client

            response = await async_authorized_client.get("/api/v1/user_data/preview")

            assert response.status_code == 200
            data = response.json()
            assert "headers" in data
            assert "previewData" in data
            assert "fileName" in data
            assert data["fileName"] == sample_user_data.filename
            assert len(data["headers"]) == 3
            assert "id" in data["headers"]

    @pytest.mark.asyncio
    async def test_get_preview_data_s3_error(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test getting preview data when S3 retrieval fails (returns error but not 500)."""
        with patch('app.api.routes.user_data.boto3.client') as mock_boto:
            mock_s3_client = MagicMock()
            mock_s3_client.get_object.side_effect = Exception("S3 error")
            mock_boto.return_value = mock_s3_client

            response = await async_authorized_client.get("/api/v1/user_data/preview")

            # Should return 200 with error field instead of failing
            assert response.status_code == 200
            data = response.json()
            assert "error" in data
            assert "Could not retrieve file from S3" in data["error"]
            assert data["fileName"] == sample_user_data.filename

    @pytest.mark.asyncio
    async def test_get_preview_data_no_data(
        self,
        async_authorized_client: AsyncClient,
        setup_database
    ):
        """Test getting preview data when user has no data."""
        response = await async_authorized_client.get("/api/v1/user_data/preview")

        assert response.status_code == 404
        assert "No data found for user" in response.json()["detail"]
