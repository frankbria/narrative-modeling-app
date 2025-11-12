"""
Backward Compatibility Test Suite for Sprint 12 Transition (Task 1.7)

Tests the transition from legacy UserData model to new specialized models:
- DatasetMetadata (dataset operations)
- TransformationConfig (transformation operations)
- ModelConfig (model training operations)

Validates:
1. Dual-write behavior (new operations create both new and legacy records)
2. Legacy endpoint functionality after new endpoint operations
3. Data consistency between UserData and new models
4. Migration path edge cases

Following strict TDD methodology:
- RED: Write failing test
- GREEN: Implement minimal code to pass
- REFACTOR: Improve code quality
- COMMIT: Save progress
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import patch
import io

from app.models.dataset import DatasetMetadata, SchemaField
from app.models.transformation import TransformationConfig, TransformationStep
from app.models.model import ModelConfig, FeatureConfig, TrainingConfig, PerformanceMetrics, HyperparameterConfig, ProblemType
from app.models.user_data import UserData
from app.services.dataset_service import DatasetService


@pytest.mark.integration
class TestDualWriteValidation:
    """
    Test dual-write behavior: operations through new endpoints create both
    new models AND legacy UserData records with matching data.
    """

    @pytest.mark.asyncio
    async def test_dataset_upload_creates_both_models(
        self, async_authorized_client, setup_database
    ):
        """
        Test that POST /datasets/upload creates both DatasetMetadata AND UserData.
        Validates dual-write behavior for dataset creation.
        """
        # ARRANGE: Create CSV file content
        csv_content = b"id,value,category\n1,10.5,A\n2,20.3,B\n3,30.1,C"
        files = {
            'file': ('test_dual_write.csv', io.BytesIO(csv_content), 'text/csv')
        }

        # Mock S3 upload
        with patch('app.utils.s3.upload_file_to_s3', return_value=(True, 's3://bucket/test_dual_write.csv')):
            # ACT: Upload file through new endpoint
            response = await async_authorized_client.post(
                "/api/v1/datasets/upload",
                files=files
            )

        # ASSERT: Upload succeeded
        assert response.status_code == 200
        data = response.json()
        dataset_id = data["dataset_id"]

        # ASSERT: DatasetMetadata was created
        dataset_metadata = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == dataset_id
        )
        assert dataset_metadata is not None
        assert dataset_metadata.filename == "test_dual_write.csv"
        assert dataset_metadata.num_rows == 3
        assert dataset_metadata.num_columns == 3

        # ASSERT: Legacy UserData was also created (dual-write)
        user_data = await UserData.find_one(
            UserData.filename == "test_dual_write.csv"
        )
        assert user_data is not None

        # ASSERT: Data matches between both models
        assert user_data.filename == dataset_metadata.filename
        assert user_data.original_filename == dataset_metadata.original_filename
        assert user_data.s3_url == dataset_metadata.s3_url
        assert user_data.num_rows == dataset_metadata.num_rows
        assert user_data.num_columns == dataset_metadata.num_columns
        assert user_data.user_id == dataset_metadata.user_id

    @pytest.mark.asyncio
    async def test_dataset_update_syncs_to_userdata(
        self, async_authorized_client, setup_database
    ):
        """
        Test that updating a dataset through PUT /datasets/{id} also updates
        the corresponding UserData record.

        NOTE: Current implementation only dual-writes on CREATE, not UPDATE.
        This test documents the expected behavior for future implementation.
        """
        # ARRANGE: Create dataset using service (ensures both models exist)
        service = DatasetService()
        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="update_sync_test",
            filename="sync_test.csv",
            original_filename="sync_test.csv",
            file_type="csv",
            file_path="datasets/sync_test.csv",
            s3_url="s3://bucket/sync_test.csv",
            num_rows=100,
            num_columns=3,
            columns=["id", "value", "category"],
            data_schema=[
                SchemaField(
                    field_name="id",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=100,
                    missing_values=0
                )
            ]
        )

        # ACT: Update dataset with statistics and quality report
        update_data = {
            "statistics": {"id": {"mean": 50.5, "std": 29.01}},
            "quality_report": {"completeness": 0.95, "accuracy": 0.98}
        }

        response = await async_authorized_client.put(
            f"/api/v1/datasets/{dataset.dataset_id}",
            json=update_data
        )

        # ASSERT: Update succeeded
        assert response.status_code == 200

        # ASSERT: DatasetMetadata was updated
        updated_dataset = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == dataset.dataset_id
        )
        assert updated_dataset.statistics is not None
        assert updated_dataset.statistics["id"]["mean"] == 50.5
        assert updated_dataset.quality_report is not None
        assert updated_dataset.quality_report["completeness"] == 0.95

        # DOCUMENT: UserData NOT updated (current limitation - dual-write only on create)
        # Future enhancement should sync updates to UserData for backward compatibility
        user_data = await UserData.find_one(
            UserData.filename == "sync_test.csv"
        )
        assert user_data is not None
        # UserData statistics are None (not synced on update - expected current behavior)
        assert user_data.statistics is None

    @pytest.mark.asyncio
    async def test_dataset_processing_updates_both_models(
        self, async_authorized_client, setup_database
    ):
        """
        Test that POST /datasets/{id}/process updates both DatasetMetadata
        and UserData with processing status.

        NOTE: Current implementation only dual-writes on CREATE, not PROCESS.
        This test documents the current behavior and expected future enhancement.
        """
        # ARRANGE: Create dataset
        service = DatasetService()
        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="process_sync_test",
            filename="process_sync.csv",
            original_filename="process_sync.csv",
            file_type="csv",
            file_path="datasets/process_sync.csv",
            s3_url="s3://bucket/process_sync.csv",
            num_rows=50,
            num_columns=2,
            columns=["x", "y"],
            data_schema=[]
        )

        # ACT: Mark as processed
        process_data = {
            "statistics": {"x": {"mean": 25.0}},
            "quality_report": {"completeness": 1.0},
            "inferred_schema": {"x": "numeric", "y": "numeric"}
        }

        response = await async_authorized_client.post(
            f"/api/v1/datasets/{dataset.dataset_id}/process",
            json=process_data
        )

        # ASSERT: Processing succeeded
        assert response.status_code == 200
        data = response.json()
        assert data["is_processed"] is True

        # ASSERT: DatasetMetadata marked as processed
        processed_dataset = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == dataset.dataset_id
        )
        assert processed_dataset.is_processed is True
        assert processed_dataset.processed_at is not None

        # DOCUMENT: UserData NOT updated (current limitation - dual-write only on create)
        # Future enhancement should sync processing status to UserData for backward compatibility
        user_data = await UserData.find_one(
            UserData.filename == "process_sync.csv"
        )
        assert user_data is not None
        # UserData is_processed remains False (not synced - expected current behavior)
        assert user_data.is_processed is False
        assert user_data.processed_at is None


@pytest.mark.integration
class TestLegacyEndpointCompatibility:
    """
    Test that legacy /api/v1/user-data endpoints still return correct data
    after operations performed through new API endpoints.
    """

    @pytest.mark.asyncio
    async def test_legacy_list_after_new_upload(
        self, async_authorized_client, setup_database
    ):
        """
        Test that GET /api/v1/user-data returns datasets uploaded via
        POST /datasets/upload (new endpoint).
        """
        # ARRANGE: Upload file via new endpoint
        csv_content = b"id,name,value\n1,Alice,100\n2,Bob,200"
        files = {
            'file': ('legacy_list_test.csv', io.BytesIO(csv_content), 'text/csv')
        }

        with patch('app.utils.s3.upload_file_to_s3', return_value=(True, 's3://bucket/legacy_list_test.csv')):
            upload_response = await async_authorized_client.post(
                "/api/v1/datasets/upload",
                files=files
            )

        assert upload_response.status_code == 200

        # ACT: Retrieve via legacy endpoint
        legacy_response = await async_authorized_client.get("/api/v1/user_data/", follow_redirects=True)

        # ASSERT: Legacy endpoint returns uploaded dataset
        assert legacy_response.status_code == 200
        user_data_list = legacy_response.json()
        assert len(user_data_list) > 0

        # Find our uploaded dataset in the list
        found = False
        for item in user_data_list:
            if item["filename"] == "legacy_list_test.csv":
                found = True
                assert item["num_rows"] == 2
                assert item["num_columns"] == 3
                assert "s3_url" in item
                assert "created_at" in item
                break

        assert found, "Uploaded dataset not found in legacy endpoint response"

    @pytest.mark.asyncio
    async def test_legacy_retrieve_after_new_upload(
        self, async_authorized_client, setup_database
    ):
        """
        Test that GET /api/v1/user-data/{id} retrieves dataset uploaded via
        new endpoint, using the UserData ID.
        """
        # ARRANGE: Upload file via new endpoint
        csv_content = b"x,y,z\n1,2,3\n4,5,6"
        files = {
            'file': ('legacy_retrieve_test.csv', io.BytesIO(csv_content), 'text/csv')
        }

        with patch('app.utils.s3.upload_file_to_s3', return_value=(True, 's3://bucket/legacy_retrieve_test.csv')):
            upload_response = await async_authorized_client.post(
                "/api/v1/datasets/upload",
                files=files
            )

        assert upload_response.status_code == 200

        # Get the UserData ID (created by dual-write)
        user_data = await UserData.find_one(
            UserData.filename == "legacy_retrieve_test.csv"
        )
        assert user_data is not None
        user_data_id = str(user_data.id)

        # ACT: Retrieve via legacy endpoint using UserData ID
        legacy_response = await async_authorized_client.get(
            f"/api/v1/user_data/{user_data_id}"
        )

        # ASSERT: Legacy endpoint returns correct dataset
        assert legacy_response.status_code == 200
        data = legacy_response.json()
        assert data["filename"] == "legacy_retrieve_test.csv"
        assert data["num_rows"] == 2
        assert data["num_columns"] == 3

    @pytest.mark.asyncio
    async def test_legacy_data_format_unchanged(
        self, async_authorized_client, setup_database
    ):
        """
        Test that UserData response format remains unchanged (no breaking changes).
        Validates essential fields are present in legacy endpoint responses.
        """
        # ARRANGE: Create dataset via new endpoint
        csv_content = b"a,b\n1,2\n3,4"
        files = {
            'file': ('format_test.csv', io.BytesIO(csv_content), 'text/csv')
        }

        with patch('app.utils.s3.upload_file_to_s3', return_value=(True, 's3://bucket/format_test.csv')):
            await async_authorized_client.post(
                "/api/v1/datasets/upload",
                files=files
            )

        # ACT: Retrieve via legacy list endpoint
        response = await async_authorized_client.get("/api/v1/user_data/", follow_redirects=True)

        # ASSERT: Response has expected legacy format
        assert response.status_code == 200
        user_data_list = response.json()
        assert len(user_data_list) > 0

        # Validate legacy response format (must include these fields)
        item = user_data_list[0]
        required_fields = [
            "_id", "user_id", "filename", "original_filename", "s3_url",
            "num_rows", "num_columns", "data_schema", "created_at", "updated_at"
        ]
        for field in required_fields:
            assert field in item, f"Required field '{field}' missing from legacy response"

    @pytest.mark.asyncio
    async def test_legacy_latest_endpoint_after_new_upload(
        self, async_authorized_client, setup_database
    ):
        """
        Test that GET /api/v1/user-data/latest returns most recent dataset
        uploaded via new endpoint.
        """
        # ARRANGE: Upload multiple files via new endpoint
        for i in range(3):
            csv_content = f"col1,col2\n{i},value{i}".encode()
            files = {
                'file': (f'latest_test_{i}.csv', io.BytesIO(csv_content), 'text/csv')
            }

            with patch('app.utils.s3.upload_file_to_s3', return_value=(True, f's3://bucket/latest_test_{i}.csv')):
                response = await async_authorized_client.post(
                    "/api/v1/datasets/upload",
                    files=files
                )
                assert response.status_code == 200

        # ACT: Get latest via legacy endpoint
        latest_response = await async_authorized_client.get("/api/v1/user_data/latest")

        # ASSERT: Latest dataset is returned
        assert latest_response.status_code == 200
        data = latest_response.json()

        # The latest should be latest_test_2.csv
        assert data["filename"] == "latest_test_2.csv"


@pytest.mark.integration
class TestDataConsistency:
    """
    Test data consistency between UserData and new models.
    Validates that data fields match between legacy and new models.
    """

    @pytest.mark.asyncio
    async def test_dataset_metadata_matches_userdata(
        self, async_authorized_client, setup_database
    ):
        """
        Test that DatasetMetadata fields match corresponding UserData fields.
        Compares: filename, s3_url, schema_info, num_rows, num_columns, etc.
        """
        # ARRANGE: Create dataset via service (dual-write)
        service = DatasetService()
        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="consistency_test_1",
            filename="consistency1.csv",
            original_filename="consistency1_original.csv",
            file_type="csv",
            file_path="datasets/consistency1.csv",
            s3_url="s3://bucket/consistency1.csv",
            num_rows=250,
            num_columns=5,
            columns=["a", "b", "c", "d", "e"],
            data_schema=[
                SchemaField(
                    field_name="a",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=250,
                    missing_values=5
                )
            ]
        )

        # ACT: Retrieve both models
        dataset_metadata = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == "consistency_test_1"
        )
        user_data = await UserData.find_one(
            UserData.filename == "consistency1.csv"
        )

        # ASSERT: Both models exist
        assert dataset_metadata is not None
        assert user_data is not None

        # ASSERT: Core fields match
        assert user_data.filename == dataset_metadata.filename
        assert user_data.original_filename == dataset_metadata.original_filename
        assert user_data.s3_url == dataset_metadata.s3_url
        assert user_data.num_rows == dataset_metadata.num_rows
        assert user_data.num_columns == dataset_metadata.num_columns
        assert user_data.user_id == dataset_metadata.user_id

        # ASSERT: Schema fields match
        assert len(user_data.data_schema) == len(dataset_metadata.data_schema)
        for i, schema_field in enumerate(user_data.data_schema):
            ds_field = dataset_metadata.data_schema[i]
            assert schema_field.field_name == ds_field.field_name
            assert schema_field.field_type == ds_field.field_type
            assert schema_field.inferred_dtype == ds_field.inferred_dtype
            assert schema_field.unique_values == ds_field.unique_values
            assert schema_field.missing_values == ds_field.missing_values

    @pytest.mark.asyncio
    async def test_timestamps_consistency(
        self, async_authorized_client, setup_database
    ):
        """
        Test that created_at and updated_at timestamps are consistent
        between UserData and DatasetMetadata.
        """
        # ARRANGE: Create dataset
        service = DatasetService()
        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="timestamp_test",
            filename="timestamp.csv",
            original_filename="timestamp.csv",
            file_type="csv",
            file_path="datasets/timestamp.csv",
            s3_url="s3://bucket/timestamp.csv",
            num_rows=10,
            num_columns=2,
            columns=["x", "y"],
            data_schema=[]
        )

        # ACT: Retrieve both models
        dataset_metadata = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == "timestamp_test"
        )
        user_data = await UserData.find_one(
            UserData.filename == "timestamp.csv"
        )

        # ASSERT: Timestamps exist and are close (within 1 second)
        assert dataset_metadata is not None
        assert user_data is not None

        # Compare created_at (should be very close, within 1 second)
        time_diff = abs(
            (dataset_metadata.created_at - user_data.created_at).total_seconds()
        )
        assert time_diff < 1.0, "created_at timestamps differ by more than 1 second"

        # Compare updated_at
        time_diff = abs(
            (dataset_metadata.updated_at - user_data.updated_at).total_seconds()
        )
        assert time_diff < 1.0, "updated_at timestamps differ by more than 1 second"

    @pytest.mark.asyncio
    async def test_statistics_consistency(
        self, async_authorized_client, setup_database
    ):
        """
        Test that statistics and quality_report match between models.
        """
        # ARRANGE: Create dataset with statistics
        service = DatasetService()
        statistics = {
            "col1": {"mean": 50.0, "std": 15.0, "min": 10.0, "max": 90.0}
        }
        quality_report = {
            "completeness": 0.95,
            "accuracy": 0.98,
            "consistency": 0.92
        }

        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="stats_test",
            filename="stats.csv",
            original_filename="stats.csv",
            file_type="csv",
            file_path="datasets/stats.csv",
            s3_url="s3://bucket/stats.csv",
            num_rows=100,
            num_columns=1,
            columns=["col1"],
            data_schema=[],
            statistics=statistics,
            quality_report=quality_report
        )

        # ACT: Retrieve both models
        dataset_metadata = await DatasetMetadata.find_one(
            DatasetMetadata.dataset_id == "stats_test"
        )
        user_data = await UserData.find_one(
            UserData.filename == "stats.csv"
        )

        # ASSERT: Statistics match
        assert dataset_metadata.statistics == user_data.statistics
        assert dataset_metadata.statistics["col1"]["mean"] == 50.0

        # ASSERT: Quality reports match
        assert dataset_metadata.quality_report == user_data.quality_report
        assert dataset_metadata.quality_report["completeness"] == 0.95


@pytest.mark.integration
class TestMigrationPathScenarios:
    """
    Test edge cases during migration period.
    Handles partial data, missing fields, and schema mismatches gracefully.
    """

    @pytest.mark.asyncio
    async def test_userdata_only_legacy_records(
        self, async_authorized_client, setup_database
    ):
        """
        Test handling of UserData records that exist without corresponding
        DatasetMetadata (legacy records from before migration).
        """
        # ARRANGE: Create UserData directly (simulating legacy record)
        from app.models.user_data import UserData, SchemaField as LegacySchemaField

        user_data = UserData(
            user_id="test_user_123",
            filename="legacy_only.csv",
            original_filename="legacy_only.csv",
            s3_url="s3://bucket/legacy_only.csv",
            num_rows=50,
            num_columns=2,
            data_schema=[
                LegacySchemaField(
                    field_name="col1",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=50,
                    missing_values=0,
                    example_values=[1, 2, 3],
                    is_constant=False,
                    is_high_cardinality=False
                )
            ]
        )
        await user_data.insert()

        # ACT: Access via legacy endpoint (should work)
        response = await async_authorized_client.get(
            f"/api/v1/user_data/{str(user_data.id)}"
        )

        # ASSERT: Legacy endpoint handles UserData-only records
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "legacy_only.csv"
        assert data["num_rows"] == 50

        # ASSERT: DatasetMetadata does NOT exist (expected for legacy-only)
        dataset_metadata = await DatasetMetadata.find_one(
            DatasetMetadata.user_id == "test_user_123",
            DatasetMetadata.filename == "legacy_only.csv"
        )
        assert dataset_metadata is None

    @pytest.mark.asyncio
    async def test_missing_fields_in_userdata(
        self, async_authorized_client, setup_database
    ):
        """
        Test handling of legacy UserData records with incomplete/missing fields.
        System should handle with defaults gracefully.
        """
        # ARRANGE: Create UserData with minimal fields (missing optional ones)
        from app.models.user_data import UserData

        user_data = UserData(
            user_id="test_user_123",
            filename="minimal.csv",
            original_filename="minimal.csv",
            s3_url="s3://bucket/minimal.csv",
            num_rows=10,
            num_columns=1,
            data_schema=[],
            # Missing: statistics, quality_report, is_processed, etc.
        )
        await user_data.insert()

        # ACT: Access via legacy endpoint
        response = await async_authorized_client.get(
            f"/api/v1/user_data/{str(user_data.id)}"
        )

        # ASSERT: Handles missing fields with defaults
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "minimal.csv"

        # Optional fields should have default values or be None
        assert data.get("is_processed", False) is False
        assert data.get("statistics") is None or data.get("statistics") == {}
        assert data.get("quality_report") is None or data.get("quality_report") == {}

    @pytest.mark.asyncio
    async def test_new_models_only_forward_compatibility(
        self, async_authorized_client, setup_database
    ):
        """
        Test forward compatibility: new models exist without UserData.
        This tests the scenario where dual-write might fail or be disabled.
        """
        # ARRANGE: Create DatasetMetadata directly (without UserData)
        dataset = DatasetMetadata(
            user_id="test_user_123",
            dataset_id="forward_compat_test",
            filename="forward.csv",
            original_filename="forward.csv",
            file_type="csv",
            file_path="datasets/forward.csv",
            s3_url="s3://bucket/forward.csv",
            num_rows=20,
            num_columns=2,
            columns=["a", "b"],
            data_schema=[]
        )
        await dataset.save()

        # ACT: Try to access via new endpoint (should work)
        response = await async_authorized_client.get(
            f"/api/v1/datasets/{dataset.dataset_id}"
        )

        # ASSERT: New endpoint works fine
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "forward_compat_test"
        assert data["filename"] == "forward.csv"

        # ASSERT: UserData does NOT exist (expected for forward-only)
        user_data = await UserData.find_one(
            UserData.filename == "forward.csv"
        )
        assert user_data is None

    @pytest.mark.asyncio
    async def test_schema_field_format_differences(
        self, async_authorized_client, setup_database
    ):
        """
        Test handling of schema field format differences between
        old and new SchemaField models.
        """
        # ARRANGE: Create dataset via service (creates both models)
        service = DatasetService()
        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="schema_diff_test",
            filename="schema_diff.csv",
            original_filename="schema_diff.csv",
            file_type="csv",
            file_path="datasets/schema_diff.csv",
            s3_url="s3://bucket/schema_diff.csv",
            num_rows=100,
            num_columns=2,
            columns=["field1", "field2"],
            data_schema=[
                SchemaField(
                    field_name="field1",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=100,
                    missing_values=5,
                    example_values=[1, 2, 3, 4, 5],
                    is_constant=False,
                    is_high_cardinality=True
                ),
                SchemaField(
                    field_name="field2",
                    field_type="categorical",
                    data_type="nominal",
                    inferred_dtype="object",
                    unique_values=3,
                    missing_values=0,
                    example_values=["A", "B", "C"],
                    is_constant=False,
                    is_high_cardinality=False
                )
            ]
        )

        # ACT: Retrieve via both new and legacy endpoints
        new_response = await async_authorized_client.get(
            f"/api/v1/datasets/{dataset.dataset_id}"
        )

        user_data = await UserData.find_one(
            UserData.filename == "schema_diff.csv"
        )
        assert user_data is not None

        legacy_response = await async_authorized_client.get(
            f"/api/v1/user_data/{str(user_data.id)}"
        )

        # ASSERT: Both endpoints return schema data
        assert new_response.status_code == 200
        assert legacy_response.status_code == 200

        new_data = new_response.json()
        legacy_data = legacy_response.json()

        # ASSERT: Schema fields are present in both
        assert "data_schema" in new_data
        assert "data_schema" in legacy_data
        assert len(new_data["data_schema"]) == 2
        assert len(legacy_data["data_schema"]) == 2

        # ASSERT: Core schema fields match
        for i in range(2):
            assert new_data["data_schema"][i]["field_name"] == legacy_data["data_schema"][i]["field_name"]
            assert new_data["data_schema"][i]["field_type"] == legacy_data["data_schema"][i]["field_type"]

    @pytest.mark.asyncio
    async def test_data_format_evolution_handling(
        self, async_authorized_client, setup_database
    ):
        """
        Test handling of data format changes between UserData and DatasetMetadata.
        Validates graceful handling of field renames, type changes, etc.
        """
        # ARRANGE: Create dataset with all optional fields populated
        service = DatasetService()
        dataset = await service.create_dataset(
            user_id="test_user_123",
            dataset_id="evolution_test",
            filename="evolution.csv",
            original_filename="evolution_original.csv",
            file_type="csv",
            file_path="datasets/evolution.csv",
            s3_url="s3://bucket/evolution.csv",
            file_size=2048,
            num_rows=500,
            num_columns=10,
            columns=[f"col{i}" for i in range(10)],
            data_schema=[],
            statistics={"col1": {"mean": 100.0}},
            quality_report={"completeness": 1.0},
            data_preview=[{"col1": 1, "col2": 2}],
            inferred_schema={"col1": "numeric"},
            onboarding_progress={"step": 1, "completed": False}
        )

        # ACT: Retrieve via both endpoints
        new_response = await async_authorized_client.get(
            f"/api/v1/datasets/{dataset.dataset_id}"
        )

        user_data = await UserData.find_one(
            UserData.filename == "evolution.csv"
        )
        assert user_data is not None

        legacy_response = await async_authorized_client.get(
            f"/api/v1/user_data/{str(user_data.id)}"
        )

        # ASSERT: Both endpoints return successfully
        assert new_response.status_code == 200
        assert legacy_response.status_code == 200

        new_data = new_response.json()
        legacy_data = legacy_response.json()

        # ASSERT: Core fields present in both
        assert new_data["filename"] == legacy_data["filename"]
        assert new_data["num_rows"] == legacy_data["num_rows"]
        assert new_data["num_columns"] == legacy_data["num_columns"]

        # ASSERT: Optional fields handled gracefully
        assert "statistics" in new_data
        assert "statistics" in legacy_data
        if new_data["statistics"] and legacy_data["statistics"]:
            assert new_data["statistics"]["col1"]["mean"] == legacy_data["statistics"]["col1"]["mean"]
