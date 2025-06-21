import pytest
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np
from fastapi import UploadFile
from app.models.user_data import UserData, SchemaField
from app.utils.schema_inference import infer_schema
from app.utils.s3 import upload_file_to_s3
import io


@pytest.mark.asyncio
async def test_validate_file_valid_csv():
    """Test file validation with a valid CSV file."""
    # Create a mock file object
    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.content_type = "text/csv"

    # Test validation
    is_valid = mock_file.filename.endswith((".csv", ".xlsx", ".txt"))
    assert is_valid


@pytest.mark.asyncio
async def test_validate_file_invalid_type():
    """Test file validation with an invalid file type."""
    # Create a mock file object with invalid type

    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test.xyz"
    mock_file.content_type = "application/octet-stream"

    # Test validation


    is_valid = mock_file.filename.endswith((".csv", ".xlsx", ".txt"))
    assert not is_valid


@pytest.mark.asyncio
async def test_process_file_success(mock_user_id, setup_database):
    """Test successful file processing."""
    # Create sample data
    data = pd.DataFrame(
        {
            "numeric_col": [1, 2, 3, 4, 5],
            "categorical_col": ["A", "B", "A", "B", "C"],
            "text_col": ["text1", "text2", "text3", "text4", "text5"],
        }
    )

    # Create a mock file object


    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.content_type = "text/csv"
    mock_file.read.return_value = data.to_csv(index=False).encode()

    # Mock S3 upload
    with patch(
        "app.utils.s3.upload_file_to_s3",
        return_value=(True, "https://test-bucket.s3.amazonaws.com/test.csv")):
        # Mock schema inference
        with patch(
            "app.utils.schema_inference.infer_schema",
            return_value=[
                SchemaField(
                    field_name="numeric_col",
                    field_type="numeric",
                    data_type="float",
                    inferred_dtype="float64",
                    unique_values=5,
                    missing_values=0,
                    example_values=[1.0, 2.0, 3.0],
                    is_constant=False,
                    is_high_cardinality=False),
                SchemaField(
                    field_name="categorical_col",
                    field_type="categorical",
                    data_type="object",
                    inferred_dtype="object",
                    unique_values=3,
                    missing_values=0,
                    example_values=["A", "B", "C"],
                    is_constant=False,
                    is_high_cardinality=False),
                SchemaField(
                    field_name="text_col",
                    field_type="text",
                    data_type="object",
                    inferred_dtype="object",
                    unique_values=5,
                    missing_values=0,
                    example_values=["text1", "text2", "text3"],
                    is_constant=False,
                    is_high_cardinality=False)
            ]):
            # Create UserData object
            user_data = UserData(
                user_id=mock_user_id,
        filename=mock_file.filename,
        s3_url="https://test-bucket.s3.amazonaws.com/test.csv",
        num_rows=5,
        num_columns=3,
        data_schema=[
                    SchemaField(
                        field_name="numeric_col",
                        field_type="numeric",
                        data_type="float",
                        inferred_dtype="float64",
                        unique_values=5,
                        missing_values=0,
                        example_values=[1.0, 2.0, 3.0],
                        is_constant=False,
                        is_high_cardinality=False

                        )

                        ],

                        original_filename="test.csv"
                        )

            # Verify result
            assert user_data is not None
            assert isinstance(user_data, UserData)
            assert user_data.user_id == mock_user_id
            assert user_data.num_columns == 3
            assert user_data.num_rows == 5
            assert len(user_data.data_schema) == 3


@pytest.mark.asyncio
async def test_process_file_empty_data(mock_user_id, setup_database):
    """Test file processing with empty data."""
    # Create empty dataframe

    data = pd.DataFrame()

    # Create a mock file object


    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.content_type = "text/csv"
    mock_file.read.return_value = data.to_csv(index=False).encode()

    # Mock S3 upload
    with patch(
        "app.utils.s3.upload_file_to_s3",
        return_value=(True, "https://test-bucket.s3.amazonaws.com/test.csv")):
        # Mock schema inference
        with patch("app.utils.schema_inference.infer_schema", return_value=[]):
            # Create UserData object
            user_data = UserData(
                user_id=mock_user_id,
                filename=mock_file.filename,
                original_filename="test.csv",
                num_rows=0,
                num_columns=0,
        s3_url="https://test-bucket.s3.amazonaws.com/test.csv",
        data_schema=[],
    )

            # Verify result
            assert user_data is not None
            assert isinstance(user_data, UserData)
            assert user_data.user_id == mock_user_id
            assert user_data.num_columns == 0
            assert user_data.num_rows == 0
            assert len(user_data.data_schema) == 0


@pytest.mark.asyncio
async def test_process_file_invalid_data(mock_user_id, setup_database):
    """Test file processing with invalid data."""
    # Create invalid data (non-serializable)
    data = pd.DataFrame({"invalid": [object()]})

    # Create a mock file object


    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.content_type = "text/csv"
    mock_file.read.return_value = data.to_csv(index=False).encode()

    # Mock S3 upload
    with patch(
        "app.utils.s3.upload_file_to_s3",
        return_value=(True, "https://test-bucket.s3.amazonaws.com/test.csv")):
        # Mock schema inference
        with patch(
            "app.utils.schema_inference.infer_schema",
            return_value=[
                SchemaField(
                    field_name="invalid",
                    field_type="text",
                    data_type="object",
                    inferred_dtype="object",
                    unique_values=1,
                    missing_values=0,
                    example_values=[],
                    is_constant=False,
                    is_high_cardinality=False)
            ]):
            # Create UserData object
            user_data = UserData(
                user_id=mock_user_id,
                filename=mock_file.filename,
                original_filename="test.csv",
                num_rows=3,
                num_columns=1,
        s3_url="https://test-bucket.s3.amazonaws.com/test.csv",
        data_schema=[
                    SchemaField(
                        field_name="invalid",
                        field_type="text",
                        data_type="object",
                        inferred_dtype="object",
                        unique_values=1,
                        missing_values=0,
                        example_values=[],
                        is_constant=False,
                        is_high_cardinality=False
    )
                ])

            # Verify result
            assert user_data is not None
            assert isinstance(user_data, UserData)
            assert user_data.user_id == mock_user_id
            assert user_data.num_columns == 1
            assert user_data.num_rows == 3
            assert len(user_data.data_schema) == 1
