"""
Integration tests for MongoDB fixtures.

These tests validate that the MongoDB fixtures work correctly and provide
proper test isolation.

Run with: pytest tests/integration/test_mongodb_fixtures.py -v -m integration
"""

import pytest
from datetime import datetime, timezone


@pytest.mark.integration
@pytest.mark.asyncio
async def test_setup_database_fixture(setup_database):
    """Test that the setup_database fixture initializes Beanie correctly."""
    from app.models.user_data import UserData

    # Verify we can query the database
    count = await UserData.find().count()
    assert count == 0, "Database should be empty at start of test"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mongo_client_fixture(mongo_client):
    """Test that the mongo_client fixture provides a working client."""
    from app.config import settings

    # Verify client is connected
    assert mongo_client is not None

    # Test database connection
    db = mongo_client[settings.TEST_MONGODB_DB]
    collections = await db.list_collection_names()
    assert isinstance(collections, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_data_fixture(test_user_data):
    """Test that test_user_data fixture creates a valid UserData document."""
    from app.models.user_data import UserData

    # Verify fixture returned a document
    assert test_user_data is not None
    assert test_user_data.id is not None

    # Verify document exists in database
    found = await UserData.get(test_user_data.id)
    assert found is not None
    assert found.user_id == "test_user_123"
    assert found.filename == "integration_test.csv"
    assert found.num_rows == 100
    assert found.num_columns == 3

    # Verify schema fields
    assert len(found.data_schema) == 3
    field_names = [field.field_name for field in found.data_schema]
    assert "id" in field_names
    assert "value" in field_names
    assert "category" in field_names


@pytest.mark.integration
@pytest.mark.asyncio
async def test_trained_model_fixture(test_trained_model, test_user_data):
    """Test that test_trained_model fixture creates a valid TrainedModel document."""
    from app.models.trained_model import TrainedModel

    # Verify fixture returned a document
    assert test_trained_model is not None
    assert test_trained_model.id is not None

    # Verify document exists in database
    found = await TrainedModel.get(test_trained_model.id)
    assert found is not None
    assert found.userId == "test_user_123"
    assert found.modelType == "classification"

    # Verify params
    assert found.params is not None
    assert found.params["algorithm"] == "random_forest"

    # Verify performance
    assert found.performance is not None
    assert "accuracy" in found.performance
    assert found.performance["accuracy"] == 0.95

    # Verify relationship to UserData (datasetId is a Link)
    assert found.datasetId is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_batch_job_fixture(test_batch_job):
    """Test that test_batch_job fixture creates a valid BatchJob document."""
    from app.models.batch_job import BatchJob, JobType, JobStatus

    # Verify fixture returned a document
    assert test_batch_job is not None
    assert test_batch_job.id is not None

    # Verify document exists in database
    found = await BatchJob.get(test_batch_job.id)
    assert found is not None
    assert found.user_id == "test_user_123"
    assert found.job_id == "test_job_123"
    assert found.job_type == JobType.MODEL_TRAINING
    assert found.status == JobStatus.PENDING

    # Verify config
    assert found.config is not None
    assert found.config["algorithm"] == "random_forest"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fixture_isolation(test_user_data):
    """Test that fixtures provide proper test isolation."""
    from app.models.user_data import UserData

    # Create additional document in this test
    additional_data = UserData(
        user_id="test_user_456",
        filename="additional_test.csv",
        original_filename="additional_test.csv",
        s3_url="s3://test-bucket/additional_test.csv",
        num_rows=50,
        num_columns=2,
        data_schema=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    await additional_data.insert()

    # Verify both documents exist
    count = await UserData.find().count()
    assert count == 2

    # Cleanup will be handled by fixtures
    await additional_data.delete()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_document_crud_operations(setup_database):
    """Test basic CRUD operations on MongoDB documents."""
    from app.models.user_data import UserData, SchemaField

    # CREATE
    user_data = UserData(
        user_id="crud_test_user",
        filename="crud_test.csv",
        original_filename="crud_test.csv",
        s3_url="s3://test-bucket/crud_test.csv",
        num_rows=10,
        num_columns=2,
        data_schema=[
            SchemaField(
                field_name="test_field",
                field_type="numeric",
                data_type="interval",
                inferred_dtype="int64",
                unique_values=10,
                missing_values=0,
                example_values=[1, 2, 3],
                is_constant=False,
                is_high_cardinality=False
            )
        ],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    await user_data.insert()
    assert user_data.id is not None

    # READ
    found = await UserData.get(user_data.id)
    assert found is not None
    assert found.filename == "crud_test.csv"

    # UPDATE
    found.num_rows = 20
    await found.save()

    updated = await UserData.get(user_data.id)
    assert updated.num_rows == 20

    # DELETE
    await updated.delete()

    deleted = await UserData.get(user_data.id)
    assert deleted is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_operations(test_user_data):
    """Test MongoDB query operations."""
    from app.models.user_data import UserData

    # Find by user_id
    results = await UserData.find(UserData.user_id == "test_user_123").to_list()
    assert len(results) == 1
    assert results[0].id == test_user_data.id

    # Find by filename pattern
    results = await UserData.find(
        UserData.filename == "integration_test.csv"
    ).to_list()
    assert len(results) == 1

    # Count documents
    count = await UserData.find(UserData.user_id == "test_user_123").count()
    assert count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_fixtures_interaction(
    test_user_data, test_trained_model, test_batch_job
):
    """Test that multiple fixtures can be used together."""
    from app.models.user_data import UserData
    from app.models.trained_model import TrainedModel
    from app.models.batch_job import BatchJob

    # Verify all fixtures are present
    assert test_user_data.id is not None
    assert test_trained_model.id is not None
    assert test_batch_job.id is not None

    # Verify relationship between fixtures (datasetId is a Link)
    assert test_trained_model.datasetId is not None

    # Verify all documents exist in database
    user_count = await UserData.find().count()
    model_count = await TrainedModel.find().count()
    job_count = await BatchJob.find().count()

    assert user_count >= 1
    assert model_count >= 1
    assert job_count >= 1
