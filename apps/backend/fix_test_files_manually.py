#!/usr/bin/env python3
"""
Manual fixes for specific test files
"""
import os

# Define manual fixes for each file
fixes = {
    "tests/test_api/test_analytics.py": """import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
from beanie import PydanticObjectId, Link
from app.models.analytics_result import AnalyticsResult
from app.models.user_data import UserData, SchemaField
from app.models.plot import Plot
from app.config import settings
from app.auth.nextauth_auth import get_current_user_id
from app.main import app


@pytest.fixture
def mock_user_id():
    return "test_user_123"


@pytest.fixture
def mock_dataset():
    return UserData(
        id=PydanticObjectId(),
        user_id="test_user_123",
        filename="test.csv",
        original_filename="test.csv",
        s3_url="s3://test-bucket/test.csv",
        num_rows=100,
        num_columns=5,
        data_schema=[
            SchemaField(
                field_name="column1",
                field_type="numeric",
                data_type="ratio",
                inferred_dtype="float64",
                unique_values=10,
                missing_values=0,
                example_values=[1.0, 2.0, 3.0],
                is_constant=False,
                is_high_cardinality=False,
            )
        ],
    )


@pytest.fixture
def mock_plot(mock_dataset):
    return Plot(
        id=PydanticObjectId(),
        userId="test_user_123",
        datasetId=Link(mock_dataset.id, document_class=UserData),
        type="scatter",
        imageUrl="https://example.com/plot.png",
        metadata={"title": "Test Plot", "description": "A test plot"},
        generatedAt=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_analytics_result(mock_dataset, mock_plot):
    return AnalyticsResult(
        userId="test_user_123",
        datasetId=mock_dataset.id,
        analysisType="EDA",
        config={"columns": ["column1", "column2"]},
        result={"summary": "Test analysis"},
        plotRefs=[mock_plot.id],
        summaryText="Test summary",
    )


@pytest.fixture
def serializable_analytics_result(sample_analytics_result):
    # Create a properly serializable dictionary
    # Extract the actual ID from Link objects
    dataset_id = sample_analytics_result.datasetId
    if hasattr(dataset_id, "ref"):
        dataset_id = dataset_id.ref.id

    plot_refs = []
    if sample_analytics_result.plotRefs:
        for ref in sample_analytics_result.plotRefs:
            if hasattr(ref, "ref"):
                plot_refs.append(str(ref.ref.id))
            else:
                plot_refs.append(str(ref))

    return {
        "userId": "test_user_123",
        "datasetId": str(dataset_id),
        "analysisType": "EDA",
        "config": {"columns": ["column1", "column2"]},
        "result": {"summary": "Test analysis"},
        "plotRefs": plot_refs,
        "summaryText": "Test summary",
    }


@pytest.fixture(autouse=True)
def mock_auth():
    \"\"\"Mock the authentication dependency.\"\"\"
    with patch("app.api.routes.analytics_result.get_current_user_id") as mock:
        mock.return_value = "test_user_123"
        yield mock


def print_debug_info(response, request_data=None):
    \"\"\"Print debug information for API calls\"\"\"
    print("\\n===== DEBUG INFO =====")
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")
    if request_data:
        print(f"Request Data: {json.dumps(request_data, indent=2)}")
    print("=====================\\n")


@pytest.mark.asyncio
async def test_create_analytics_result(
    async_test_client,
    mock_user_id,
    mock_dataset,
    mock_plot,
    serializable_analytics_result,
    setup_database,
):
    # Create required objects first
    await mock_dataset.insert()
    await mock_plot.insert()

    # Print the serializable data for debugging
    print(f"Serializable data: {json.dumps(serializable_analytics_result, indent=2)}")

    response = await async_test_client.post(
        "/api/analytics/", json=serializable_analytics_result
    )
    print_debug_info(response, serializable_analytics_result)
    assert response.status_code == 200
    data = response.json()
    assert data["userId"] == mock_user_id
    assert data["analysisType"] == "EDA"


@pytest.mark.asyncio
async def test_get_analytics_results(
    async_test_client, mock_user_id, sample_analytics_result, setup_database
):
    await sample_analytics_result.insert()

    response = await async_test_client.get("/api/analytics/")
    print_debug_info(response)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["userId"] == mock_user_id


@pytest.mark.asyncio
async def test_get_analytics_result(
    async_test_client, mock_user_id, sample_analytics_result, setup_database
):
    await sample_analytics_result.insert()

    response = await async_test_client.get(
        f"/api/analytics/{sample_analytics_result.id}"
    )
    print_debug_info(response)
    assert response.status_code == 200
    data = response.json()
    assert data["userId"] == mock_user_id
    assert data["analysisType"] == "EDA"


@pytest.mark.asyncio
async def test_update_analytics_result(
    async_test_client,
    mock_user_id,
    sample_analytics_result,
    serializable_analytics_result,
    setup_database,
):
    await sample_analytics_result.insert()

    # Update the analysis type
    serializable_analytics_result["analysisType"] = "regression"

    response = await async_test_client.put(
        f"/api/analytics/{sample_analytics_result.id}",
        json=serializable_analytics_result,
    )
    print_debug_info(response, serializable_analytics_result)
    assert response.status_code == 200
    data = response.json()
    assert data["analysisType"] == "regression"


@pytest.mark.asyncio
async def test_delete_analytics_result(
    async_test_client, mock_user_id, sample_analytics_result, setup_database
):
    await sample_analytics_result.insert()

    response = await async_test_client.delete(
        f"/api/analytics/{sample_analytics_result.id}"
    )
    print_debug_info(response)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_get_nonexistent_result(async_test_client, mock_user_id, setup_database):
    nonexistent_id = PydanticObjectId()
    response = await async_test_client.get(f"/api/analytics/{nonexistent_id}")
    print_debug_info(response)
    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied"


@pytest.mark.asyncio
async def test_unauthorized_access(
    async_test_client, sample_analytics_result, setup_database
):
    # Insert with one user ID
    await sample_analytics_result.insert()

    # Save the current override and replace it temporarily.
    original_override = app.dependency_overrides.get(get_current_user_id)
    app.dependency_overrides[get_current_user_id] = lambda: "different_user_123"

    try:
        response = await async_test_client.get(
            f"/api/analytics/{sample_analytics_result.id}"
        )
        print_debug_info(response)
        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"
    finally:
        # Restore the original override so other tests are not affected.
        if original_override is not None:
            app.dependency_overrides[get_current_user_id] = original_override
        else:
            app.dependency_overrides.pop(get_current_user_id, None)
""",
}

def main():
    for file_path, content in fixes.items():
        print(f"Fixing {file_path}")
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"✅ Fixed {file_path}")

if __name__ == "__main__":
    main()