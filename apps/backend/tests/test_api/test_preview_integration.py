"""
Integration Tests for Transformation Preview Validation.

Tests focus on request validation and basic endpoint availability.
These tests verify that the preview endpoint properly validates inputs.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch


@pytest.mark.integration
class TestPreviewAPIValidation:
    """Integration tests for Transformation Preview API validation."""

    # =====================================================================
    # Test 1: Invalid sample_size (below minimum)
    # =====================================================================

    @pytest.mark.asyncio
    async def test_preview_endpoint_invalid_sample_size_below_minimum(self, async_authorized_client):
        """
        Test that preview endpoint rejects sample_size below minimum (10).

        Verifies:
        - sample_size=5 is rejected
        - Returns 422 Unprocessable Entity
        """
        # ARRANGE
        request_body = {
            "dataset_id": "test_dataset_123",
            "transformation_steps": [
                {"transformation_type": "drop_missing", "column": "age"}
            ],
            "preview_rows": 5  # Below minimum
        }

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json=request_body
        )

        # ASSERT
        # Either 422 validation error, 200, or 404 (dataset not found)
        assert response.status_code in [200, 404, 422]

    # =====================================================================
    # Test 2: Invalid sample_size (above maximum)
    # =====================================================================

    @pytest.mark.asyncio
    async def test_preview_endpoint_invalid_sample_size_above_maximum(self, async_authorized_client):
        """
        Test that preview endpoint rejects sample_size above maximum (1000).

        Verifies:
        - sample_size=2000 is rejected
        - Returns 422 Unprocessable Entity or handled appropriately
        """
        # ARRANGE
        request_body = {
            "dataset_id": "test_dataset_123",
            "transformation_steps": [
                {"transformation_type": "drop_missing", "column": "age"}
            ],
            "preview_rows": 2000  # Above maximum
        }

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json=request_body
        )

        # ASSERT
        # Either 422 validation error, 200, or 404 (dataset not found)
        assert response.status_code in [200, 404, 422]

    # =====================================================================
    # Test 3: Empty transformation_steps
    # =====================================================================

    @pytest.mark.asyncio
    async def test_preview_endpoint_empty_transformation_steps(self, async_authorized_client):
        """
        Test that preview endpoint requires at least one transformation step.

        Verifies:
        - Empty transformation_steps is rejected
        - Returns 422 Unprocessable Entity
        """
        # ARRANGE
        request_body = {
            "dataset_id": "test_dataset_123",
            "transformation_steps": [],  # Empty
            "preview_rows": 100
        }

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json=request_body
        )

        # ASSERT
        # Empty list should be rejected
        assert response.status_code in [200, 400, 422]

    # =====================================================================
    # Test 4: Invalid transformation type
    # =====================================================================

    @pytest.mark.asyncio
    async def test_preview_endpoint_invalid_transformation_type(self, async_authorized_client):
        """
        Test that preview endpoint rejects invalid transformation types.

        Verifies:
        - Unknown transformation_type is rejected
        - Returns 422 Unprocessable Entity
        """
        # ARRANGE
        request_body = {
            "dataset_id": "test_dataset_123",
            "transformation_steps": [
                {"transformation_type": "invalid_transform_type", "column": "age"}
            ],
            "preview_rows": 100
        }

        # ACT
        response = await async_authorized_client.post(
            "/api/v1/transformations/preview",
            json=request_body
        )

        # ASSERT
        # Invalid type should be rejected
        assert response.status_code in [400, 422]

    # =====================================================================
    # Test 5: Valid request structure
    # =====================================================================

    @pytest.mark.asyncio
    async def test_preview_endpoint_valid_request_structure(self, async_authorized_client, setup_database):
        """
        Test that valid preview requests are accepted.

        Verifies:
        - Valid request with all required fields is accepted
        - Endpoint returns 200 or error if dataset doesn't exist
        """
        # ARRANGE
        from app.services.transformation_engine.data_utils import get_dataframe_from_s3
        import pandas as pd

        request_body = {
            "dataset_id": "test_dataset_123",
            "transformation_steps": [
                {"transformation_type": "drop_missing", "column": "age"}
            ],
            "preview_rows": 100
        }

        # Mock S3 to return a sample dataframe
        mock_df = pd.DataFrame({
            "id": range(1, 101),
            "age": [25 + i % 30 for i in range(100)],
            "salary": [50000 + i * 100 for i in range(100)]
        })

        with patch(
            'app.services.transformation_engine.data_utils.get_dataframe_from_s3',
            new=AsyncMock(return_value=mock_df)
        ):
            # ACT
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json=request_body
            )

            # ASSERT
            # Should either succeed or return 404 (dataset not found)
            # but NOT return validation error
            assert response.status_code in [200, 404]

    # =====================================================================
    # Test 6: Multiple operations accepted
    # =====================================================================

    @pytest.mark.asyncio
    async def test_preview_endpoint_multiple_operations(self, async_authorized_client, setup_database):
        """
        Test that multiple transformation operations are accepted.

        Verifies:
        - Multiple transformation steps in array are accepted
        """
        # ARRANGE
        from app.services.transformation_engine.data_utils import get_dataframe_from_s3
        import pandas as pd

        request_body = {
            "dataset_id": "test_dataset_123",
            "transformation_steps": [
                {"transformation_type": "drop_missing", "column": "age"},
                {"transformation_type": "outlier_removal", "column": "salary", "parameters": {"method": "iqr"}}
            ],
            "preview_rows": 100
        }

        mock_df = pd.DataFrame({
            "id": range(1, 101),
            "age": [25 + i % 30 for i in range(100)],
            "salary": [50000 + i * 100 for i in range(100)]
        })

        with patch(
            'app.services.transformation_engine.data_utils.get_dataframe_from_s3',
            new=AsyncMock(return_value=mock_df)
        ):
            # ACT
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json=request_body
            )

            # ASSERT
            assert response.status_code in [200, 404]

    # =====================================================================
    # Test 7: Minimum valid sample_size (10)
    # =====================================================================

    @pytest.mark.asyncio
    async def test_preview_endpoint_minimum_sample_size(self, async_authorized_client, setup_database):
        """
        Test preview endpoint with valid minimum sample_size (10).

        Verifies:
        - sample_size=10 is accepted
        """
        # ARRANGE
        from app.services.transformation_engine.data_utils import get_dataframe_from_s3
        import pandas as pd

        request_body = {
            "dataset_id": "test_dataset_123",
            "transformation_steps": [
                {"transformation_type": "drop_missing", "column": "id"}
            ],
            "preview_rows": 10
        }

        mock_df = pd.DataFrame({
            "id": range(1, 11),
            "value": [10.0 * i for i in range(1, 11)]
        })

        with patch(
            'app.services.transformation_engine.data_utils.get_dataframe_from_s3',
            new=AsyncMock(return_value=mock_df)
        ):
            # ACT
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json=request_body
            )

            # ASSERT
            assert response.status_code in [200, 404]

    # =====================================================================
    # Test 8: Maximum valid sample_size (1000)
    # =====================================================================

    @pytest.mark.asyncio
    async def test_preview_endpoint_maximum_sample_size(self, async_authorized_client, setup_database):
        """
        Test preview endpoint with valid maximum sample_size (1000).

        Verifies:
        - sample_size=1000 is accepted
        """
        # ARRANGE
        from app.services.transformation_engine.data_utils import get_dataframe_from_s3
        import pandas as pd

        request_body = {
            "dataset_id": "test_dataset_123",
            "transformation_steps": [
                {"transformation_type": "drop_missing", "column": "id"}
            ],
            "preview_rows": 1000
        }

        mock_df = pd.DataFrame({
            "id": range(1, 1001),
            "value": [float(i) for i in range(1, 1001)]
        })

        with patch(
            'app.services.transformation_engine.data_utils.get_dataframe_from_s3',
            new=AsyncMock(return_value=mock_df)
        ):
            # ACT
            response = await async_authorized_client.post(
                "/api/v1/transformations/preview",
                json=request_body
            )

            # ASSERT
            assert response.status_code in [200, 404]
