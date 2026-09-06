"""
Test suite for User Data API endpoints.

Integration tests for user_data routes covering all endpoints:
- POST / - retired, 410 Gone (#451)
- GET / - List all user data for user
- GET /latest - Get most recent user data
- GET /{id} - Get specific user data by ID
- GET /preview - Get preview data with S3 file content
- PUT /{id} - Update user data
- DELETE /{id} - Delete user data
- GET /{id}/ai-summary - Get AI summary
- GET /{id}/eda-summary - Get EDA summary
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from beanie import PydanticObjectId
from httpx import AsyncClient

from app.models.user_data import AISummary, SchemaField, UserData


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
        """POST / is retired (#451).

        It asserted a create round-trip through a body that let the client name
        `s3_url`, which was the vulnerability. The endpoint answers 410; the
        replacement coverage lives in TestUserDataMassAssignment, and datasets
        are created through POST /api/v1/upload.
        """
        response = await async_authorized_client.post(
            "/api/v1/user_data/",
            json={
                "filename": "new_dataset.csv",
                "original_filename": "new_dataset.csv",
                "s3_url": f"s3://test-bucket/datasets/{mock_user_id}/new_dataset.csv",
                "num_rows": 50,
                "num_columns": 2,
                "data_schema": [],
            },
        )

        assert response.status_code == 410

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
        """Test accessing another user's data returns 404 (#451)."""
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

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

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
        # num_rows describes the stored file and is computed by the pipeline, so
        # it is not client-settable since #451 — the sent 150 is ignored.
        assert data["num_rows"] == sample_user_data.num_rows

    @pytest.mark.asyncio
    async def test_update_user_data_access_denied(
        self,
        async_authorized_client: AsyncClient,
        setup_database
    ):
        """Test updating another user's data returns 404.

        Was 403 until #451: that confirmed the row existed and belonged to
        someone else. Unknown and foreign now answer identically.
        """
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

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

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
        """Test deleting another user's data returns 404 (#451)."""
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

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

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
        """Test accessing another user's AI summary returns 404 (#451)."""
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

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

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
        """Test accessing another user's EDA summary returns 404 (#451)."""
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

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_preview_data_with_s3_success(
        self,
        async_authorized_client: AsyncClient,
        sample_user_data: UserData
    ):
        """Test getting preview data with successful S3 retrieval."""
        import io

        import pandas as pd

        # Mock S3 client and response
        mock_df = pd.DataFrame({
            "id": [1, 2, 3],
            "value": [10.5, 20.3, 15.7],
            "category": ["A", "B", "C"]
        })
        csv_buffer = io.BytesIO()
        mock_df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        with patch('app.api.routes.user_data.create_s3_client') as mock_create_client:
            mock_s3_client = MagicMock()
            mock_s3_client.get_object.return_value = {
                "Body": MagicMock(read=MagicMock(return_value=csv_content))
            }
            mock_create_client.return_value = mock_s3_client

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
        with patch('app.api.routes.user_data.create_s3_client') as mock_create_client:
            mock_s3_client = MagicMock()
            mock_s3_client.get_object.side_effect = Exception("S3 error")
            mock_create_client.return_value = mock_s3_client

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


OTHER_USER = "other_user_451"


class TestUserDataMassAssignment:
    """Issue #451 (P0.8).

    `POST /` and `PUT /{id}` took the Beanie Document itself as the request
    body, so every field was client-settable — including `s3_url`, which the
    visualization and preview endpoints later fetch. A tenant could name another
    tenant's object and read it back through a legitimately-scoped endpoint.
    """

    @pytest.fixture
    async def my_dataset(self, setup_database, mock_user_id: str) -> UserData:
        doc = UserData(
            user_id=mock_user_id,
            filename="mine.csv",
            original_filename="mine.csv",
            s3_url="s3://test-bucket/mine-owned-object.csv",
            num_rows=10,
            num_columns=1,
            data_schema=[],
        )
        await doc.insert()
        return doc

    @pytest.fixture
    async def foreign_dataset(self, setup_database) -> UserData:
        doc = UserData(
            user_id=OTHER_USER,
            filename="victim.csv",
            original_filename="victim.csv",
            s3_url="s3://test-bucket/victims-secret-payroll.csv",
            num_rows=10,
            num_columns=1,
            data_schema=[],
        )
        await doc.insert()
        yield doc
        await UserData.find(UserData.user_id == OTHER_USER).delete()

    @pytest.mark.asyncio
    async def test_create_is_gone(
        self, async_authorized_client: AsyncClient, setup_database
    ):
        """POST existed only to register a client-named S3 URL, which is the
        vulnerability itself. Retired rather than narrowed (#451)."""
        response = await async_authorized_client.post(
            "/api/v1/user_data/",
            json={
                "filename": "x.csv",
                "original_filename": "x.csv",
                "s3_url": "s3://test-bucket/victims-secret-payroll.csv",
                "num_rows": 1,
                "num_columns": 1,
                "data_schema": [],
            },
        )

        assert response.status_code == 410
        assert "upload" in response.json()["detail"].lower()
        # and nothing was written
        assert await UserData.find(UserData.filename == "x.csv").count() == 0

    @pytest.mark.asyncio
    async def test_update_ignores_a_client_supplied_s3_url(
        self, async_authorized_client: AsyncClient, my_dataset: UserData,
        foreign_dataset: UserData,
    ):
        """The core exploit: repoint my own row at the victim's object."""
        original = my_dataset.s3_url

        response = await async_authorized_client.put(
            f"/api/v1/user_data/{my_dataset.id}",
            json={
                "filename": "mine.csv",
                "original_filename": "mine.csv",
                "s3_url": foreign_dataset.s3_url,
                "num_rows": 10,
                "num_columns": 1,
                "data_schema": [],
            },
        )

        assert response.status_code == 200
        reloaded = await UserData.get(my_dataset.id)
        assert reloaded.s3_url == original
        assert "victims-secret-payroll" not in reloaded.s3_url

    @pytest.mark.asyncio
    async def test_update_ignores_a_client_supplied_user_id(
        self, async_authorized_client: AsyncClient, my_dataset: UserData,
        mock_user_id: str,
    ):
        """AC2: ownership is server-authoritative, never taken from the body."""
        response = await async_authorized_client.put(
            f"/api/v1/user_data/{my_dataset.id}",
            json={
                "filename": "mine.csv",
                "original_filename": "mine.csv",
                "user_id": OTHER_USER,
                "num_rows": 10,
                "num_columns": 1,
                "data_schema": [],
            },
        )

        assert response.status_code == 200
        reloaded = await UserData.get(my_dataset.id)
        assert reloaded.user_id == mock_user_id

    @pytest.mark.asyncio
    async def test_update_still_applies_legitimate_fields(
        self, async_authorized_client: AsyncClient, my_dataset: UserData
    ):
        """Regression guard: the safe fields must still be updatable."""
        response = await async_authorized_client.put(
            f"/api/v1/user_data/{my_dataset.id}",
            json={
                "filename": "renamed.csv",
                "original_filename": "renamed.csv",
                "num_rows": 99,
            },
        )

        assert response.status_code == 200
        reloaded = await UserData.get(my_dataset.id)
        assert reloaded.filename == "renamed.csv"
        assert reloaded.original_filename == "renamed.csv"
        # num_rows is pipeline-computed, so the sent 99 is ignored (#451, AC2)
        assert reloaded.num_rows == 10

    @pytest.mark.asyncio
    async def test_update_of_another_tenants_row_is_404(
        self, async_authorized_client: AsyncClient, foreign_dataset: UserData
    ):
        """403 confirms the row exists; 404 does not."""
        response = await async_authorized_client.put(
            f"/api/v1/user_data/{foreign_dataset.id}",
            json={
                "filename": "hijacked.csv",
                "original_filename": "hijacked.csv",
                "num_rows": 1,
                "num_columns": 1,
                "data_schema": [],
            },
        )

        assert response.status_code == 404
        reloaded = await UserData.get(foreign_dataset.id)
        assert reloaded.filename == "victim.csv"

    @pytest.mark.asyncio
    async def test_update_with_an_explicit_null_does_not_brick_the_row(
        self, async_authorized_client: AsyncClient, my_dataset: UserData
    ):
        """An explicit JSON `null` counts as "set" for `exclude_unset`.

        Without `exclude_none` this wrote None onto a required field: the save
        committed, then every later read of that row failed to validate, so the
        caller's own list and preview endpoints 500'd from then on. Verified
        against the pre-fix code, which returned 500 here and left
        `filename: None` in Mongo.
        """
        # ACT
        response = await async_authorized_client.put(
            f"/api/v1/user_data/{my_dataset.id}",
            json={"filename": None, "original_filename": "kept.csv"},
        )

        # ASSERT — the null is ignored, the real value applied
        assert response.status_code == 200
        reloaded = await UserData.get(my_dataset.id)
        assert reloaded.filename == "mine.csv"
        assert reloaded.original_filename == "kept.csv"

        # and the row is still readable through the endpoints that validate it
        listing = await async_authorized_client.get("/api/v1/user_data/")
        assert listing.status_code == 200

    @pytest.mark.asyncio
    async def test_update_response_is_shaped_like_the_get_endpoints(
        self, async_authorized_client: AsyncClient, my_dataset: UserData
    ):
        """PUT returned the raw Beanie document; the GETs return UserDataResponse.

        A consistency fix, not an exposure one: `UserDataResponse` already
        carries `file_path`, `pii_report`, `quality_report` and `statistics`, so
        the only field the document adds is Beanie's internal `revision_id`.
        Stated explicitly because a review claimed the opposite.
        """
        response = await async_authorized_client.put(
            f"/api/v1/user_data/{my_dataset.id}",
            json={"filename": "renamed.csv"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["filename"] == "renamed.csv"
        assert "revision_id" not in body
        assert isinstance(body["_id"], str)

class TestS3BucketAllowlist:
    """Issue #451, AC3 — defense in depth behind the schema fix.

    `s3_url` is no longer settable from a request, but `get_file_from_s3` is
    reached from several paths and a stored URL is only as trustworthy as
    whatever wrote it.
    """

    @pytest.mark.asyncio
    async def test_refuses_a_bucket_outside_the_allowlist(self, monkeypatch):
        from app.utils.s3 import get_file_from_s3

        monkeypatch.setenv("AWS_BUCKET_NAME", "our-own-bucket")
        with patch("app.utils.s3.get_s3_client", return_value=MagicMock()) as client:
            with pytest.raises(ValueError, match="not permitted"):
                get_file_from_s3("s3://someone-elses-bucket/payroll.csv")
            client.return_value.download_fileobj.assert_not_called()

    @pytest.mark.asyncio
    async def test_fails_closed_when_no_bucket_is_configured(self, monkeypatch):
        """An unset bucket must deny, not wave everything through."""
        from app.utils.s3 import get_file_from_s3

        for var in ("AWS_BUCKET_NAME", "S3_BUCKET_NAME", "AWS_S3_BUCKET"):
            monkeypatch.delenv(var, raising=False)
        with patch("app.utils.s3.get_s3_client", return_value=MagicMock()) as client:
            with pytest.raises(ValueError, match="No S3 bucket is configured"):
                get_file_from_s3("s3://any-bucket/x.csv")
            client.return_value.download_fileobj.assert_not_called()

    @pytest.mark.asyncio
    async def test_allows_the_configured_bucket(self, monkeypatch):
        """Regression guard: the legitimate path must still download."""
        from app.utils.s3 import get_file_from_s3

        monkeypatch.setenv("AWS_BUCKET_NAME", "our-own-bucket")
        with patch("app.utils.s3.get_s3_client", return_value=MagicMock()) as client:
            get_file_from_s3("s3://our-own-bucket/mine.csv")
            client.return_value.download_fileobj.assert_called_once()
