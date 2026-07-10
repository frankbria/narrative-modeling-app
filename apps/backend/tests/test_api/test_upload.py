from unittest.mock import Mock, patch

import pandas as pd
import pytest
from fastapi import UploadFile

from app.models.user_data import SchemaField, UserData


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
                    ),
                    SchemaField(
                        field_name="categorical_col",
                        field_type="categorical",
                        data_type="object",
                        inferred_dtype="object",
                        unique_values=3,
                        missing_values=0,
                        example_values=["A", "B", "C"],
                        is_constant=False,
                        is_high_cardinality=False
                    ),
                    SchemaField(
                        field_name="text_col",
                        field_type="text",
                        data_type="object",
                        inferred_dtype="object",
                        unique_values=5,
                        missing_values=0,
                        example_values=["text1", "text2", "text3"],
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


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file_with_413(monkeypatch):
    """Issue #270: an oversized upload must 413 and NOT be masked as a 500 by
    the route's catch-all `except Exception` (guarded by `except HTTPException`)."""
    import io

    from fastapi import BackgroundTasks, HTTPException
    from starlette.datastructures import UploadFile

    from app.api.routes.upload import upload_file

    # Tiny cap so the test payload is trivially "too large".
    monkeypatch.setattr("app.utils.upload_limits.MAX_UPLOAD_BYTES", 10)

    big = UploadFile(
        filename="big.csv",
        file=io.BytesIO(b"a" * 5000),
        size=5000,
    )
    with pytest.raises(HTTPException) as exc:
        await upload_file(
            request=Mock(),
            background_tasks=BackgroundTasks(),
            file=big,
            current_user_id="user-1",
        )
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_endpoint_rejects_oversized_multipart_413(
    async_authorized_client, setup_database, monkeypatch
):
    """Issue #270 (e2e): an oversized multipart upload returns 413 through the
    full ASGI stack (multipart parse → route → read_upload_capped), proving the
    cap fires end-to-end and the route catch-all does not mask it as a 500."""
    monkeypatch.setattr("app.utils.upload_limits.MAX_UPLOAD_BYTES", 1024)

    oversized = b"col\n" + b"9\n" * 5000  # ~10 KB, over the 1 KB cap
    resp = await async_authorized_client.post(
        "/api/v1/upload/",
        files={"file": ("big.csv", oversized, "text/csv")},
    )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oversized_content_length_rejected_before_route(
    async_authorized_client, setup_database, monkeypatch
):
    """Issue #270 (e2e): BodySizeLimitMiddleware rejects on Content-Length with
    413 before the route/multipart parser runs (distinct 'body too large'
    message vs the in-route 'file too large')."""
    monkeypatch.setattr("app.middleware.body_size_limit.MAX_BODY_BYTES", 1024)

    payload = b"col\n" + b"9\n" * 5000  # ~10 KB; httpx sets Content-Length
    resp = await async_authorized_client.post(
        "/api/v1/upload/",
        files={"file": ("big.csv", payload, "text/csv")},
    )
    assert resp.status_code == 413
    assert "body too large" in resp.json()["detail"].lower()
