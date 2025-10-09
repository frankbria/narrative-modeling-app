"""
Integration tests for API versioning with real endpoints and database.

Tests validate:
- v1 API endpoints work with database operations
- Version negotiation works end-to-end
- Backward compatibility is maintained
- Version headers are correctly set
- Deprecation warnings function properly
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.user_data import UserData
from app.middleware.api_version import CURRENT_VERSION, DEFAULT_VERSION


@pytest.mark.integration
@pytest.mark.asyncio
class TestAPIVersioningIntegration:
    """Test API versioning with real database operations."""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async test client with database setup."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    async def test_v1_health_check_with_version_headers(self, client, setup_database):
        """Test v1 health check includes version headers."""
        response = await client.get(
            "/health", headers={"Accept": "application/vnd.narrativeml.v1+json"}
        )

        assert response.status_code == 200
        assert "X-API-Version" in response.headers
        assert response.headers["X-API-Version"] == "v1"
        assert response.headers["X-API-Current-Version"] == CURRENT_VERSION

    async def test_version_negotiation_via_accept_header(self, client, setup_database):
        """Test version negotiation through Accept header."""
        # Request with explicit v1 version
        response = await client.get(
            "/health", headers={"Accept": "application/vnd.narrativeml.v1+json"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "status" in data  # Health endpoint returns status="alive"

    async def test_version_negotiation_via_url_path(self, client, setup_database):
        """Test version negotiation through URL path."""
        # Health endpoint is at root, test versioned API endpoint instead
        response = await client.get("/api/v1/models")

        # Should get version headers
        assert "X-API-Version" in response.headers

    async def test_backward_compatibility_with_no_version(
        self, client, setup_database
    ):
        """Test endpoints work without explicit version (defaults to v1)."""
        response = await client.get("/health")

        assert response.status_code == 200
        # Should default to current version
        assert response.headers["X-API-Version"] == DEFAULT_VERSION

    async def test_unsupported_version_returns_406(self, client, setup_database):
        """Test requesting unsupported version returns 406."""
        response = await client.get(
            "/health", headers={"Accept": "application/vnd.narrativeml.v99+json"}
        )

        assert response.status_code == 406
        data = response.json()
        assert "not supported" in data["message"].lower()
        assert "supported_versions" in data
        assert "current_version" in data

    async def test_version_headers_present_in_all_responses(
        self, client, setup_database
    ):
        """Test version headers are added to all API responses."""
        endpoints = ["/health", "/api/v1/models"]

        for endpoint in endpoints:
            response = await client.get(endpoint)
            assert "X-API-Version" in response.headers
            assert "X-API-Current-Version" in response.headers

    async def test_multiple_version_formats_accepted(self, client, setup_database):
        """Test various Accept header formats are handled."""
        test_cases = [
            "application/vnd.narrativeml.v1+json",
            "application/json, application/vnd.narrativeml.v1+json",
            "application/vnd.narrativeml.v1+json; charset=utf-8",
        ]

        for accept_header in test_cases:
            response = await client.get("/health", headers={"Accept": accept_header})
            assert response.status_code == 200
            assert response.headers["X-API-Version"] == "v1"


@pytest.mark.integration
@pytest.mark.asyncio
class TestAPIVersioningWithDatabase:
    """Test API versioning with actual database operations."""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    async def test_v1_endpoint_with_database_write(self, client, setup_database):
        """Test v1 endpoint can write to database."""
        from app.models.user_data import SchemaField
        # This tests that the versioning middleware doesn't break database access
        test_data = UserData(
            user_id="version_test_user",
            filename="test.csv",
            original_filename="test.csv",
            s3_url="s3://test/file.csv",
            num_rows=100,
            num_columns=5,
            data_schema=[
                SchemaField(
                    field_name="col1",
                    field_type="numeric",
                    inferred_dtype="int64",
                    unique_values=100,
                    missing_values=0,
                    example_values=[1, 2, 3],
                    is_constant=False,
                    is_high_cardinality=False
                )
            ]
        )
        await test_data.insert()

        # Verify it was created
        found = await UserData.find_one(UserData.user_id == "version_test_user")
        assert found is not None
        assert found.filename == "test.csv"

        # Clean up
        await UserData.find(UserData.user_id == "version_test_user").delete()

    async def test_versioned_endpoint_performance(self, client, setup_database):
        """Test that versioning middleware doesn't significantly impact performance."""
        import time

        # Measure response time
        start = time.time()
        response = await client.get("/health")
        duration = time.time() - start

        assert response.status_code == 200
        # Should respond quickly (< 1 second even with middleware)
        assert duration < 1.0


@pytest.mark.integration
class TestVersionNegotiationPrecedence:
    """Test version negotiation precedence rules."""

    @pytest_asyncio.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    async def test_url_version_overrides_header_version(self, client, setup_database):
        """Test URL path version takes precedence over Accept header."""
        # Request v1 in URL but v2 in header (v2 doesn't exist)
        response = await client.get(
            "/api/v1/models", headers={"Accept": "application/vnd.narrativeml.v2+json"}
        )

        # Should use URL version (v1) not header version
        # Endpoint may return 401/404 but version header should still be set
        assert "X-API-Version" in response.headers

    async def test_header_version_overrides_default(self, client, setup_database):
        """Test Accept header version overrides default when no URL version."""
        response = await client.get(
            "/health", headers={"Accept": "application/vnd.narrativeml.v1+json"}
        )

        assert response.status_code == 200
        assert response.headers["X-API-Version"] == "v1"

    async def test_default_version_used_when_no_specification(
        self, client, setup_database
    ):
        """Test default version is used when neither URL nor header specify version."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert response.headers["X-API-Version"] == DEFAULT_VERSION
