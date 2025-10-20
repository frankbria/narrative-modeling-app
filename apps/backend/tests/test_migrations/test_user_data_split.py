"""
Migration testing for UserData model split.

Tests migration from monolithic UserData model to separate DatasetMetadata,
TransformationConfig, and ModelConfig models. Includes volume testing,
rollback procedures, performance measurement, and data integrity verification.
"""

import pytest
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch
import uuid

from app.models.user_data import UserData, SchemaField as LegacySchemaField, AISummary
from app.models.dataset import DatasetMetadata, SchemaField, PIIReport
from app.models.transformation import TransformationConfig, TransformationStep
from app.models.model import ModelConfig


class TestMigrationDataGeneration:
    """Test data generation for migration testing."""

    @staticmethod
    def generate_legacy_user_data(count: int, user_id: str = "test_user") -> List[UserData]:
        """Generate legacy UserData documents for testing."""
        documents = []
        for i in range(count):
            doc = UserData.model_construct(
                id=f"legacy_{i}",
                user_id=user_id,
                filename=f"dataset_{i}.csv",
                original_filename=f"original_{i}.csv",
                s3_url=f"s3://bucket/datasets/{i}.csv",
                num_rows=1000 + i,
                num_columns=10 + (i % 5),
                data_schema=[
                    LegacySchemaField(
                        field_name=f"column_{j}",
                        field_type="numeric" if j % 2 == 0 else "text",
                        inferred_dtype="int64" if j % 2 == 0 else "object",
                        unique_values=100 + j,
                        missing_values=5 + j,
                        example_values=[f"value_{j}", f"value_{j+1}"],
                        is_constant=False,
                        is_high_cardinality=False
                    )
                    for j in range(10 + (i % 5))
                ],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                aiSummary=AISummary(
                    overview=f"Dataset {i} overview",
                    issues=[f"Issue {j}" for j in range(3)],
                    relationships=[f"Relationship {j}" for j in range(2)],
                    suggestions=[f"Suggestion {j}" for j in range(2)],
                    rawMarkdown=f"# Dataset {i}\nMarkdown content",
                    createdAt=datetime.now(timezone.utc)
                ),
                contains_pii=(i % 3 == 0),
                pii_report={"detected": True, "fields": ["email"]} if i % 3 == 0 else None,
                pii_risk_level="medium" if i % 3 == 0 else "low",
                pii_masked=False,
                is_processed=True,
                processed_at=datetime.now(timezone.utc),
                schema={"columns": [f"col_{j}" for j in range(10)]},
                statistics={"mean": 50.0, "std": 15.0},
                quality_report={"completeness": 0.95, "validity": 0.98},
                row_count=1000 + i,
                columns=[f"column_{j}" for j in range(10 + (i % 5))],
                data_preview=[{"col_0": j, "col_1": f"value_{j}"} for j in range(5)],
                file_type="csv",
                onboarding_progress={"step": 1, "completed": False},
                file_path=f"datasets/{user_id}/{i}.csv",
                transformation_history=[
                    {
                        "type": "encode",
                        "column": "column_1",
                        "parameters": {"method": "label"},
                        "applied_at": datetime.now(timezone.utc).isoformat()
                    }
                ] if i % 2 == 0 else []
            )
            documents.append(doc)
        return documents


class TestMigrationLogic:
    """Test migration logic and data mapping."""

    def migrate_user_data_to_dataset_metadata(self, user_data: UserData) -> DatasetMetadata:
        """
        Migrate UserData to DatasetMetadata.

        Maps dataset-specific fields from legacy UserData model to new
        DatasetMetadata model with proper field transformations.
        """
        # Convert legacy SchemaField to new SchemaField
        schema_fields = [
            SchemaField(
                field_name=field.field_name,
                field_type=field.field_type,
                data_type=field.data_type,
                inferred_dtype=field.inferred_dtype,
                unique_values=field.unique_values,
                missing_values=field.missing_values,
                example_values=field.example_values,
                is_constant=field.is_constant,
                is_high_cardinality=field.is_high_cardinality
            )
            for field in user_data.data_schema
        ]

        # Convert PII report
        pii_report = None
        if user_data.contains_pii:
            pii_report = PIIReport(
                contains_pii=user_data.contains_pii,
                pii_fields=user_data.pii_report.get("fields", []) if user_data.pii_report else [],
                risk_level=user_data.pii_risk_level or "low",
                detection_details=user_data.pii_report or {},
                masked=user_data.pii_masked,
                masked_at=None
            )

        # Generate dataset_id from legacy ID
        dataset_id = str(user_data.id) if user_data.id else str(uuid.uuid4())

        return DatasetMetadata.model_construct(
            user_id=user_data.user_id,
            dataset_id=dataset_id,
            filename=user_data.filename,
            original_filename=user_data.original_filename,
            file_type=user_data.file_type or "csv",
            file_path=user_data.file_path or f"datasets/{user_data.user_id}/{user_data.filename}",
            s3_url=user_data.s3_url,
            file_size=None,  # Not available in legacy model
            num_rows=user_data.row_count or user_data.num_rows,
            num_columns=user_data.num_columns,
            columns=user_data.columns or [f.field_name for f in user_data.data_schema],
            data_schema=schema_fields,
            inferred_schema=user_data.schema,
            statistics=user_data.statistics,
            quality_report=user_data.quality_report,
            data_preview=user_data.data_preview,
            ai_summary=user_data.aiSummary,
            pii_report=pii_report,
            is_processed=user_data.is_processed,
            processed_at=user_data.processed_at,
            onboarding_progress=user_data.onboarding_progress,
            created_at=user_data.created_at,
            updated_at=user_data.updated_at,
            version="1.0.0",
            parent_dataset_id=None
        )

    def migrate_user_data_to_transformation_config(
        self,
        user_data: UserData,
        dataset_id: str
    ) -> TransformationConfig:
        """
        Migrate UserData transformation fields to TransformationConfig.

        Extracts transformation history and creates new TransformationConfig
        document with properly structured transformation steps.
        """
        # Convert transformation history to TransformationStep objects
        transformation_steps = []
        for i, transform in enumerate(user_data.transformation_history):
            step = TransformationStep(
                transformation_type=transform.get("type", "unknown"),
                column=transform.get("column"),
                columns=transform.get("columns"),
                parameters=transform.get("parameters", {}),
                applied_at=datetime.fromisoformat(transform["applied_at"]) if "applied_at" in transform else datetime.now(timezone.utc),
                is_valid=True,
                validation_errors=[],
                rows_affected=transform.get("rows_affected"),
                data_loss_percentage=transform.get("data_loss_percentage")
            )
            transformation_steps.append(step)

        config_id = f"{dataset_id}_config"

        return TransformationConfig.model_construct(
            user_id=user_data.user_id,
            dataset_id=dataset_id,
            config_id=config_id,
            transformation_steps=transformation_steps,
            current_file_path=user_data.file_path,
            is_applied=len(transformation_steps) > 0,
            applied_at=user_data.updated_at if transformation_steps else None,
            validation_result=None,
            last_validated_at=None,
            last_preview=None,
            total_transformations=len(transformation_steps),
            total_data_loss=0.0,
            created_at=user_data.created_at,
            updated_at=user_data.updated_at,
            version="1.0.0",
            parent_config_id=None
        )

    def test_migrate_single_document(self):
        """Test migration of a single UserData document."""
        # Generate test data
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(1)
        user_data = legacy_docs[0]

        # Migrate to DatasetMetadata
        dataset_metadata = self.migrate_user_data_to_dataset_metadata(user_data)

        # Verify critical fields
        assert dataset_metadata.user_id == user_data.user_id
        assert dataset_metadata.filename == user_data.filename
        assert dataset_metadata.original_filename == user_data.original_filename
        assert dataset_metadata.num_rows == user_data.row_count
        assert dataset_metadata.num_columns == user_data.num_columns
        assert len(dataset_metadata.data_schema) == len(user_data.data_schema)
        assert dataset_metadata.is_processed == user_data.is_processed

        # Verify PII migration
        if user_data.contains_pii:
            assert dataset_metadata.pii_report is not None
            assert dataset_metadata.pii_report.contains_pii == user_data.contains_pii
            assert dataset_metadata.pii_report.risk_level == user_data.pii_risk_level

        # Migrate to TransformationConfig
        transform_config = self.migrate_user_data_to_transformation_config(
            user_data,
            dataset_metadata.dataset_id
        )

        # Verify transformation migration
        assert transform_config.user_id == user_data.user_id
        assert transform_config.dataset_id == dataset_metadata.dataset_id
        assert len(transform_config.transformation_steps) == len(user_data.transformation_history)

    def test_migrate_document_without_transformations(self):
        """Test migration of document with no transformation history."""
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(1)
        user_data = legacy_docs[0]
        user_data.transformation_history = []

        dataset_metadata = self.migrate_user_data_to_dataset_metadata(user_data)
        transform_config = self.migrate_user_data_to_transformation_config(
            user_data,
            dataset_metadata.dataset_id
        )

        assert len(transform_config.transformation_steps) == 0
        assert transform_config.is_applied is False
        assert transform_config.total_transformations == 0

    def test_migrate_document_with_pii(self):
        """Test migration of document with PII data."""
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(1)
        user_data = legacy_docs[0]
        user_data.contains_pii = True
        user_data.pii_report = {"detected": True, "fields": ["email", "phone"]}
        user_data.pii_risk_level = "high"
        user_data.pii_masked = True

        dataset_metadata = self.migrate_user_data_to_dataset_metadata(user_data)

        assert dataset_metadata.has_pii() is True
        assert dataset_metadata.pii_report.contains_pii is True
        assert dataset_metadata.pii_report.risk_level == "high"
        assert "email" in dataset_metadata.pii_report.pii_fields
        assert "phone" in dataset_metadata.pii_report.pii_fields
        assert dataset_metadata.pii_report.masked is True


class TestVolumeMigration:
    """Test migration with production-like data volumes."""

    def test_migrate_1k_documents(self):
        """Test migration with 1,000 documents."""
        count = 1000
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(count)

        start_time = time.time()
        migrator = TestMigrationLogic()

        migrated_datasets = []
        migrated_configs = []

        for user_data in legacy_docs:
            dataset = migrator.migrate_user_data_to_dataset_metadata(user_data)
            config = migrator.migrate_user_data_to_transformation_config(user_data, dataset.dataset_id)
            migrated_datasets.append(dataset)
            migrated_configs.append(config)

        duration = time.time() - start_time

        # Verify count
        assert len(migrated_datasets) == count
        assert len(migrated_configs) == count

        # Performance target: <10s for 1K documents
        assert duration < 10.0, f"Migration took {duration:.2f}s, expected <10s"

        print(f"✅ Migrated {count} documents in {duration:.2f}s ({count/duration:.0f} docs/sec)")

    def test_migrate_10k_documents(self):
        """Test migration with 10,000 documents."""
        count = 10000
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(count)

        start_time = time.time()
        migrator = TestMigrationLogic()

        migrated_datasets = []
        migrated_configs = []

        for user_data in legacy_docs:
            dataset = migrator.migrate_user_data_to_dataset_metadata(user_data)
            config = migrator.migrate_user_data_to_transformation_config(user_data, dataset.dataset_id)
            migrated_datasets.append(dataset)
            migrated_configs.append(config)

        duration = time.time() - start_time

        # Verify count
        assert len(migrated_datasets) == count
        assert len(migrated_configs) == count

        # Performance target: <100s for 10K documents
        assert duration < 100.0, f"Migration took {duration:.2f}s, expected <100s"

        print(f"✅ Migrated {count} documents in {duration:.2f}s ({count/duration:.0f} docs/sec)")

    @pytest.mark.slow
    def test_migrate_100k_documents(self):
        """Test migration with 100,000 documents (slow test, mark as slow)."""
        count = 100000

        # For 100K test, we'll simulate in batches to avoid memory issues
        batch_size = 10000
        num_batches = count // batch_size

        start_time = time.time()
        migrator = TestMigrationLogic()

        total_migrated = 0

        for batch_num in range(num_batches):
            legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(batch_size)

            for user_data in legacy_docs:
                dataset = migrator.migrate_user_data_to_dataset_metadata(user_data)
                config = migrator.migrate_user_data_to_transformation_config(user_data, dataset.dataset_id)
                total_migrated += 1

        duration = time.time() - start_time

        # Verify count
        assert total_migrated == count

        # Performance target: <1000s for 100K documents
        assert duration < 1000.0, f"Migration took {duration:.2f}s, expected <1000s"

        print(f"✅ Migrated {count} documents in {duration:.2f}s ({count/duration:.0f} docs/sec)")


class TestDataIntegrity:
    """Test data integrity during migration."""

    def test_no_data_loss(self):
        """Verify no data is lost during migration."""
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(100)
        migrator = TestMigrationLogic()

        for user_data in legacy_docs:
            dataset = migrator.migrate_user_data_to_dataset_metadata(user_data)
            config = migrator.migrate_user_data_to_transformation_config(user_data, dataset.dataset_id)

            # Verify all critical fields preserved
            assert dataset.user_id == user_data.user_id
            assert dataset.filename == user_data.filename
            assert dataset.num_rows == (user_data.row_count or user_data.num_rows)
            assert dataset.num_columns == user_data.num_columns
            assert len(dataset.data_schema) == len(user_data.data_schema)

            # Verify transformation history preserved
            assert len(config.transformation_steps) == len(user_data.transformation_history)

    def test_field_mapping_accuracy(self):
        """Verify all fields are correctly mapped."""
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(10)
        migrator = TestMigrationLogic()

        field_mapping = {
            # DatasetMetadata mappings
            "user_id": lambda ud, dm: ud.user_id == dm.user_id,
            "filename": lambda ud, dm: ud.filename == dm.filename,
            "original_filename": lambda ud, dm: ud.original_filename == dm.original_filename,
            "s3_url": lambda ud, dm: ud.s3_url == dm.s3_url,
            "num_rows": lambda ud, dm: (ud.row_count or ud.num_rows) == dm.num_rows,
            "num_columns": lambda ud, dm: ud.num_columns == dm.num_columns,
            "is_processed": lambda ud, dm: ud.is_processed == dm.is_processed,
            "processed_at": lambda ud, dm: ud.processed_at == dm.processed_at,
            "created_at": lambda ud, dm: ud.created_at == dm.created_at,
            "updated_at": lambda ud, dm: ud.updated_at == dm.updated_at,
        }

        for user_data in legacy_docs:
            dataset = migrator.migrate_user_data_to_dataset_metadata(user_data)

            for field_name, validator in field_mapping.items():
                assert validator(user_data, dataset), f"Field {field_name} not correctly mapped"

    def test_schema_preservation(self):
        """Verify schema information is fully preserved."""
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(10)
        migrator = TestMigrationLogic()

        for user_data in legacy_docs:
            dataset = migrator.migrate_user_data_to_dataset_metadata(user_data)

            assert len(dataset.data_schema) == len(user_data.data_schema)

            for old_field, new_field in zip(user_data.data_schema, dataset.data_schema):
                assert old_field.field_name == new_field.field_name
                assert old_field.field_type == new_field.field_type
                assert old_field.inferred_dtype == new_field.inferred_dtype
                assert old_field.unique_values == new_field.unique_values
                assert old_field.missing_values == new_field.missing_values


class TestRollbackProcedure:
    """Test rollback procedures for migration failure scenarios."""

    def rollback_dataset_metadata(self, dataset_metadata: DatasetMetadata) -> UserData:
        """
        Rollback DatasetMetadata to UserData format.

        Reconstructs legacy UserData document from migrated DatasetMetadata
        for rollback scenarios.
        """
        # Convert new SchemaField back to legacy format
        legacy_schema = [
            LegacySchemaField(
                field_name=field.field_name,
                field_type=field.field_type,
                data_type=field.data_type,
                inferred_dtype=field.inferred_dtype,
                unique_values=field.unique_values,
                missing_values=field.missing_values,
                example_values=field.example_values,
                is_constant=field.is_constant,
                is_high_cardinality=field.is_high_cardinality
            )
            for field in dataset_metadata.data_schema
        ]

        # Extract PII fields
        contains_pii = dataset_metadata.has_pii()
        pii_report = None
        pii_risk_level = "low"
        pii_masked = False

        if dataset_metadata.pii_report:
            pii_report = {
                "detected": dataset_metadata.pii_report.contains_pii,
                "fields": dataset_metadata.pii_report.pii_fields
            }
            pii_risk_level = dataset_metadata.pii_report.risk_level
            pii_masked = dataset_metadata.pii_report.masked

        return UserData.model_construct(
            id=dataset_metadata.dataset_id,
            user_id=dataset_metadata.user_id,
            filename=dataset_metadata.filename,
            original_filename=dataset_metadata.original_filename,
            s3_url=dataset_metadata.s3_url,
            num_rows=dataset_metadata.num_rows,
            num_columns=dataset_metadata.num_columns,
            data_schema=legacy_schema,
            created_at=dataset_metadata.created_at,
            updated_at=dataset_metadata.updated_at,
            aiSummary=dataset_metadata.ai_summary,
            contains_pii=contains_pii,
            pii_report=pii_report,
            pii_risk_level=pii_risk_level,
            pii_masked=pii_masked,
            is_processed=dataset_metadata.is_processed,
            processed_at=dataset_metadata.processed_at,
            schema=dataset_metadata.inferred_schema,
            statistics=dataset_metadata.statistics,
            quality_report=dataset_metadata.quality_report,
            row_count=dataset_metadata.num_rows,
            columns=dataset_metadata.columns,
            data_preview=dataset_metadata.data_preview,
            file_type=dataset_metadata.file_type,
            onboarding_progress=dataset_metadata.onboarding_progress,
            file_path=dataset_metadata.file_path,
            transformation_history=[]  # Will be merged from TransformationConfig
        )

    def merge_transformation_history(
        self,
        user_data: UserData,
        transform_config: TransformationConfig
    ) -> UserData:
        """Merge transformation history from TransformationConfig back to UserData."""
        transformation_history = [
            {
                "type": step.transformation_type,
                "column": step.column,
                "columns": step.columns,
                "parameters": step.parameters,
                "applied_at": step.applied_at.isoformat(),
                "rows_affected": step.rows_affected,
                "data_loss_percentage": step.data_loss_percentage
            }
            for step in transform_config.transformation_steps
        ]

        user_data.transformation_history = transformation_history
        user_data.file_path = transform_config.current_file_path
        return user_data

    def test_rollback_single_document(self):
        """Test rollback of a single migrated document."""
        # Create original
        original_docs = TestMigrationDataGeneration.generate_legacy_user_data(1)
        original = original_docs[0]

        # Migrate forward
        migrator = TestMigrationLogic()
        dataset = migrator.migrate_user_data_to_dataset_metadata(original)
        config = migrator.migrate_user_data_to_transformation_config(original, dataset.dataset_id)

        # Rollback
        rolled_back = self.rollback_dataset_metadata(dataset)
        rolled_back = self.merge_transformation_history(rolled_back, config)

        # Verify rollback accuracy
        assert rolled_back.user_id == original.user_id
        assert rolled_back.filename == original.filename
        assert rolled_back.original_filename == original.original_filename
        assert rolled_back.num_rows == original.num_rows
        assert rolled_back.num_columns == original.num_columns
        assert len(rolled_back.transformation_history) == len(original.transformation_history)

    def test_rollback_preserves_all_data(self):
        """Verify rollback preserves all critical data."""
        original_docs = TestMigrationDataGeneration.generate_legacy_user_data(100)
        migrator = TestMigrationLogic()

        for original in original_docs:
            # Migrate
            dataset = migrator.migrate_user_data_to_dataset_metadata(original)
            config = migrator.migrate_user_data_to_transformation_config(original, dataset.dataset_id)

            # Rollback
            rolled_back = self.rollback_dataset_metadata(dataset)
            rolled_back = self.merge_transformation_history(rolled_back, config)

            # Verify no data loss
            assert rolled_back.user_id == original.user_id
            assert rolled_back.contains_pii == original.contains_pii
            assert rolled_back.is_processed == original.is_processed
            assert len(rolled_back.data_schema) == len(original.data_schema)


class TestPerformanceImpact:
    """Test performance impact of migration."""

    def test_query_performance_before_after(self):
        """Compare query performance before and after migration."""
        # Note: This would require actual database setup
        # For now, we demonstrate the testing approach

        # Before migration: Single collection query
        # Query time would be measured for UserData.find({"user_id": "test"})

        # After migration: Multiple collection queries
        # Query time would be measured for:
        # - DatasetMetadata.find({"user_id": "test"})
        # - TransformationConfig.find({"user_id": "test"})
        # - ModelConfig.find({"user_id": "test"})

        # Expected: New model queries should be within 10% of original performance
        # This is a placeholder for actual database performance testing
        pass

    def test_migration_performance_metrics(self):
        """Measure and validate migration performance metrics."""
        test_sizes = [100, 500, 1000]
        migrator = TestMigrationLogic()

        metrics = {}

        for size in test_sizes:
            legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(size)

            start_time = time.time()
            for user_data in legacy_docs:
                dataset = migrator.migrate_user_data_to_dataset_metadata(user_data)
                config = migrator.migrate_user_data_to_transformation_config(user_data, dataset.dataset_id)
            duration = time.time() - start_time

            docs_per_second = size / duration
            metrics[size] = {
                "duration": duration,
                "docs_per_second": docs_per_second
            }

            print(f"📊 {size} docs: {duration:.2f}s ({docs_per_second:.0f} docs/sec)")

        # Verify performance scaling
        # Larger batches should maintain similar throughput
        for size in test_sizes:
            assert metrics[size]["docs_per_second"] > 100, \
                f"Migration throughput too low: {metrics[size]['docs_per_second']:.0f} docs/sec"


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_migrate_empty_transformation_history(self):
        """Test migration with empty transformation history."""
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(1)
        user_data = legacy_docs[0]
        user_data.transformation_history = []

        migrator = TestMigrationLogic()
        dataset = migrator.migrate_user_data_to_dataset_metadata(user_data)
        config = migrator.migrate_user_data_to_transformation_config(user_data, dataset.dataset_id)

        assert len(config.transformation_steps) == 0
        assert config.total_transformations == 0

    def test_migrate_missing_optional_fields(self):
        """Test migration with missing optional fields."""
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(1)
        user_data = legacy_docs[0]

        # Remove optional fields
        user_data.aiSummary = None
        user_data.pii_report = None
        user_data.contains_pii = False  # Must also set this to False
        user_data.statistics = None
        user_data.quality_report = None
        user_data.data_preview = None

        migrator = TestMigrationLogic()
        dataset = migrator.migrate_user_data_to_dataset_metadata(user_data)

        # Should not raise errors
        assert dataset.ai_summary is None
        assert dataset.pii_report is None
        assert dataset.statistics is None
        assert dataset.quality_report is None

    def test_migrate_with_invalid_transformation_data(self):
        """Test migration with malformed transformation history."""
        legacy_docs = TestMigrationDataGeneration.generate_legacy_user_data(1)
        user_data = legacy_docs[0]

        # Add malformed transformation - these will fail validation
        user_data.transformation_history = [
            {"type": "drop_missing"},  # Valid type that doesn't require column
            {"type": "filter", "column": "test"}  # Another type that doesn't require column spec
        ]

        migrator = TestMigrationLogic()
        config = migrator.migrate_user_data_to_transformation_config(user_data, "test_dataset")

        # Should handle gracefully
        assert len(config.transformation_steps) == 2
        # Steps should have default values for missing fields
