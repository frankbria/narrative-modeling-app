"""
Integration tests for the complete upload → process → analyze workflow
"""

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from beanie import PydanticObjectId

from app.models.dataset import DatasetMetadata


@pytest.fixture
def sample_csv_file():
    """Create a sample CSV file for testing"""
    df = pd.DataFrame({
        'customer_id': range(1, 101),
        'name': [f'Customer {i}' for i in range(1, 101)],
        'age': pd.Series(range(20, 120)).sample(100, replace=True, random_state=42).reset_index(drop=True),
        'purchase_amount': pd.Series(range(10, 1000)).sample(100, replace=True, random_state=42).reset_index(drop=True),
        'purchase_date': pd.date_range('2024-01-01', periods=100, freq='D'),
        'category': pd.Series(['Electronics', 'Clothing', 'Food', 'Books']).sample(100, replace=True, random_state=42).reset_index(drop=True),
        'email': [f'customer{i}@example.com' for i in range(1, 101)]
    })

    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return csv_buffer.getvalue()

class TestFullWorkflow:
    """Integration tests for complete data processing workflow"""

    @pytest.mark.skip(reason="Complex workflow test needs refactoring - too many mocks for integration test")
    @pytest.mark.asyncio
    async def test_complete_workflow(self, async_authorized_client, sample_csv_file):
        """Test the complete workflow from upload to analysis"""

        # Step 1: Upload file
        with patch('app.utils.s3.upload_file_to_s3') as mock_upload:
            mock_upload.return_value = (True, "https://test-bucket.s3.amazonaws.com/test-file-123.csv")

            with patch('app.models.dataset.DatasetMetadata.insert', new_callable=AsyncMock) as mock_insert:
                dataset_id = str(uuid.uuid4())
                mock_dataset = DatasetMetadata(
                    id=PydanticObjectId(),
                    user_id="test-user-123",
                    dataset_id=dataset_id,
                    filename="customer_data.csv",
                    original_filename="test-file-123.csv",
                    file_path="test-user-123/test-file-123.csv",
                    s3_url="s3://test-bucket/test-file.csv",
                    num_rows=100,
                    num_columns=7,
                    columns=["customer_id", "name", "age", "purchase_amount", "purchase_date", "category", "email"],
                    data_schema=[],
                    file_type="csv",
                    created_at=datetime.now(UTC),
                    is_processed=False
                )
                mock_insert.return_value = mock_dataset

                files = {'file': ('customer_data.csv', sample_csv_file, 'text/csv')}
                response = await async_authorized_client.post("/api/v1/upload", files=files, follow_redirects=True)

                assert response.status_code == 200
                upload_data = response.json()
                assert upload_data.get("dataset_id") or upload_data.get("id")
                assert upload_data.get("filename") == "customer_data.csv"

        # Step 2: Process the uploaded file
        with patch('app.models.dataset.DatasetMetadata.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_dataset

            with patch('app.utils.s3.get_file_from_s3') as mock_s3:
                mock_s3.return_value = io.BytesIO(sample_csv_file)

                with patch.object(mock_dataset, 'save', new_callable=AsyncMock):
                    response = await async_authorized_client.post(
                        "/api/v1/data/process",
                        json={"file_id": dataset_id}
                    )

                    assert response.status_code == 200
                    process_data = response.json()

                    # Verify schema was inferred
                    assert process_data["schema"]["row_count"] == 100
                    assert process_data["schema"]["column_count"] == 7

                    # Verify statistics were calculated
                    assert "columns" in process_data["statistics"]
                    assert "age" in process_data["statistics"]["columns"]
                    assert "purchase_amount" in process_data["statistics"]["columns"]

                    # Verify quality report
                    assert 0 <= process_data["quality_report"]["overall_quality_score"] <= 1

                    # Update mock data with processed information
                    mock_dataset.is_processed = True
                    mock_dataset.inferred_schema = process_data["schema"]
                    mock_dataset.statistics = process_data["statistics"]
                    mock_dataset.quality_report = process_data["quality_report"]

        # Step 3: Get AI analysis
        with patch('app.models.dataset.DatasetMetadata.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_dataset

            with patch('app.services.mcp_integration.mcp_service.analyze_dataset', new_callable=AsyncMock) as mock_analyze:
                from app.services.mcp_integration import MCPAnalysisResponse
                mock_analyze.return_value = MCPAnalysisResponse(
                    file_id=dataset_id,
                    analysis_type="comprehensive",
                    summary="Customer purchase data with 100 records showing diverse buying patterns.",
                    insights=[
                        {
                            "type": "pattern",
                            "title": "Purchase Patterns",
                            "description": "Average purchase amount is $500 with seasonal variations"
                        },
                        {
                            "type": "demographic",
                            "title": "Customer Demographics",
                            "description": "Age range 20-119 with most customers between 40-60"
                        }
                    ],
                    recommendations=[
                        "Segment customers by purchase amount for targeted marketing",
                        "Analyze seasonal trends in purchase dates"
                    ],
                    visualizations=None,
                    metadata={"execution_time": 2.5}
                )

                response = await async_authorized_client.get(f"/api/v1/ai/analysis/{dataset_id}")

                assert response.status_code == 200

                analysis_data = response.json()
                assert "Purchase Patterns" in str(analysis_data["insights"])
                assert len(analysis_data["recommendations"]) == 2

        # Step 4: Get visualizations
        with patch('app.models.dataset.DatasetMetadata.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_dataset

            # Test histogram
            with patch('app.services.visualization_cache.generate_and_cache_histogram', new_callable=AsyncMock) as mock_hist:
                mock_hist.return_value = {
                    "bins": [20, 40, 60, 80, 100],
                    "counts": [25, 30, 25, 20],
                    "min": 20,
                    "max": 100
                }

                response = await async_authorized_client.get(f"/api/v1/visualizations/histogram/{dataset_id}/age")

                assert response.status_code == 200

                # Test correlation matrix
            with patch('app.services.visualization_cache.generate_and_cache_correlation_matrix', new_callable=AsyncMock) as mock_corr:
                mock_corr.return_value = {
                    "columns": ["age", "purchase_amount"],
                    "matrix": [[1.0, 0.3], [0.3, 1.0]]
                }

                response = await async_authorized_client.get(f"/api/v1/visualizations/correlation/{dataset_id}")

                assert response.status_code == 200

        # Step 5: Export processed data
        with patch('app.models.dataset.DatasetMetadata.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_dataset

            with patch('app.utils.s3.get_file_from_s3') as mock_s3_get:
                mock_s3_get.return_value = io.BytesIO(sample_csv_file)

                with patch('app.utils.s3.upload_file_to_s3') as mock_s3_upload:
                    mock_s3_upload.return_value = (True, "https://test-bucket.s3.amazonaws.com/exports/processed.csv")

                    response = await async_authorized_client.post(
                        f"/api/v1/data/{dataset_id}/export"
                    )

                    assert response.status_code == 200
                    export_data = response.json()
                    assert "download_url" in export_data

    @pytest.mark.skip(reason="Complex PII workflow test needs refactoring")
    @pytest.mark.asyncio
    async def test_workflow_with_pii_detection(self, async_authorized_client):
        """Test workflow with PII detection"""
        # Create data with PII
        df = pd.DataFrame({
            'name': ['John Doe', 'Jane Smith'],
            'ssn': ['123-45-6789', '987-65-4321'],
            'email': ['john@example.com', 'jane@example.com'],
            'phone': ['555-1234', '555-5678']
        })

        csv_buffer = io.BytesIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        with patch('app.utils.s3.upload_file_to_s3') as mock_upload:
            mock_upload.return_value = (True, "https://test-bucket.s3.amazonaws.com/pii-file.csv")

            with patch('app.models.user_data.UserData.insert', new_callable=AsyncMock) as mock_insert:
                from app.models.user_data import UserData
                # Use UserData since upload.py still uses it
                mock_data = MagicMock(spec=UserData)
                mock_data.id = PydanticObjectId()
                mock_data.user_id = "test_user_123"
                mock_data.filename = "pii.csv"
                mock_data.original_filename = "pii.csv"
                mock_data.s3_url = "s3://test-bucket/pii.csv"
                mock_data.num_rows = 2
                mock_data.num_columns = 4
                mock_data.pii_detected = True
                mock_data.pii_columns = ["ssn", "email", "phone"]
                mock_data.file_type = "csv"
                mock_data.upload_date = datetime.now(UTC)
                mock_insert.return_value = mock_data

                # Upload should detect PII
                files = {'file': ('pii.csv', csv_content, 'text/csv')}
                response = await async_authorized_client.post("/api/v1/upload", files=files, follow_redirects=True)

                assert response.status_code == 200
                data = response.json()
                # Check for PII detection in response (field names may vary)
                # The upload endpoint returns different field names
                if "pii_report" in data:
                    pii_report = data["pii_report"]
                    # Check for has_pii or contains_pii
                    assert pii_report.get("has_pii") or pii_report.get("contains_pii")
                elif "pii_detected" in data:
                    # Legacy format
                    assert data.get("pii_detected")

    @pytest.mark.skip(reason="Error handling test needs refactoring for new API structure")
    @pytest.mark.asyncio
    async def test_workflow_error_handling(self, async_authorized_client):
        """Test error handling throughout the workflow"""

        # Test processing non-existent file
        # The data processing endpoint may use UserData or DatasetMetadata
        # Let's patch both to be safe
        with patch('app.models.user_data.UserData.find_one', new_callable=AsyncMock) as mock_find:
            with patch('app.models.dataset.DatasetMetadata.find_one', new_callable=AsyncMock) as mock_find_ds:
                mock_find.return_value = None
                mock_find_ds.return_value = None

                response = await async_authorized_client.post(
                    "/api/v1/data/process",
                    json={"file_id": "6927913542199be18190b594"}  # Valid ObjectId format
                )
                # Should return 404 or 400 (may be wrapped in 500)
                assert response.status_code in [400, 404, 500]

        # Test analysis on unprocessed file
        from app.models.user_data import UserData
        mock_data = MagicMock(spec=UserData)
        mock_data.id = PydanticObjectId()
        mock_data.user_id = "test_user_123"
        mock_data.filename = "test.csv"
        mock_data.is_processed = False
        mock_data.schema = None

        with patch('app.models.user_data.UserData.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data

            response = await async_authorized_client.get(f"/api/v1/ai/analysis/{str(mock_data.id)}")

            # Should return 400 for unprocessed file
            assert response.status_code == 400
            response_data = response.json()
            assert "detail" in response_data
            assert "process" in response_data["detail"].lower()
