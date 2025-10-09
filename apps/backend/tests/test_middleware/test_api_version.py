"""
Unit tests for API versioning middleware.

Tests validate:
- Version parsing from Accept header
- Version parsing from URL path
- Default version behavior
- Unsupported version handling
- Deprecation warnings
- Version headers in responses
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware.api_version import (
    APIVersionMiddleware,
    get_api_version,
    SUPPORTED_VERSIONS,
    CURRENT_VERSION,
    DEFAULT_VERSION,
)


@pytest.mark.unit
class TestAPIVersionMiddleware:
    """Test API version middleware."""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app with versioning middleware."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            version = get_api_version(request)
            return {"version": version}

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_default_version(self, client):
        """Test default version is used when none specified."""
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["version"] == DEFAULT_VERSION
        assert response.headers["X-API-Version"] == DEFAULT_VERSION
        assert response.headers["X-API-Current-Version"] == CURRENT_VERSION

    def test_version_from_accept_header(self, client):
        """Test version parsing from Accept header."""
        response = client.get(
            "/test",
            headers={"Accept": "application/vnd.narrativeml.v1+json"}
        )

        assert response.status_code == 200
        assert response.json()["version"] == "v1"
        assert response.headers["X-API-Version"] == "v1"

    def test_version_from_url_path(self, client):
        """Test version parsing from URL path takes precedence."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        @app.get("/api/v1/test")
        async def versioned_endpoint(request: Request):
            version = get_api_version(request)
            return {"version": version}

        client = TestClient(app)
        response = client.get(
            "/api/v1/test",
            headers={"Accept": "application/vnd.narrativeml.v2+json"}
        )

        # URL version (v1) takes precedence over header version (v2)
        assert response.status_code == 200
        assert response.json()["version"] == "v1"

    def test_unsupported_version_from_header(self, client):
        """Test unsupported version returns 406."""
        response = client.get(
            "/test",
            headers={"Accept": "application/vnd.narrativeml.v99+json"}
        )

        assert response.status_code == 406
        assert "not supported" in response.json()["message"]
        assert response.json()["supported_versions"] == SUPPORTED_VERSIONS
        assert response.json()["current_version"] == CURRENT_VERSION

    def test_unsupported_version_from_path(self, client):
        """Test unsupported version in path returns 406."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        @app.get("/api/v99/test")
        async def versioned_endpoint(request: Request):
            return {"version": get_api_version(request)}

        client = TestClient(app)
        response = client.get("/api/v99/test")

        assert response.status_code == 406

    def test_current_version_no_deprecation(self, client):
        """Test current version doesn't have deprecation warning."""
        response = client.get(
            "/test",
            headers={"Accept": f"application/vnd.narrativeml.{CURRENT_VERSION}+json"}
        )

        assert response.status_code == 200
        assert "Warning" not in response.headers
        assert "Deprecation" not in response.headers

    def test_old_version_deprecation_warning(self, client):
        """Test old version includes deprecation warning."""
        # This test assumes v1 will become old when v2 is released
        # For now, if CURRENT_VERSION == "v1", this test will pass trivially
        if CURRENT_VERSION == "v1":
            # Skip test - no old versions yet
            pytest.skip("No deprecated versions exist yet")

        response = client.get(
            "/test",
            headers={"Accept": "application/vnd.narrativeml.v1+json"}
        )

        assert response.status_code == 200
        assert "Warning" in response.headers
        assert "deprecated" in response.headers["Warning"].lower()
        assert response.headers["Deprecation"] == "true"

    def test_invalid_accept_header_uses_default(self, client):
        """Test invalid Accept header falls back to default."""
        response = client.get(
            "/test",
            headers={"Accept": "application/json"}
        )

        assert response.status_code == 200
        assert response.json()["version"] == DEFAULT_VERSION

    def test_version_pattern_parsing(self, client):
        """Test various Accept header patterns."""
        test_cases = [
            ("application/vnd.narrativeml.v1+json", "v1"),
            ("application/json, application/vnd.narrativeml.v1+json", "v1"),
            ("application/vnd.narrativeml.v1+json; charset=utf-8", "v1"),
        ]

        for accept_header, expected_version in test_cases:
            response = client.get("/test", headers={"Accept": accept_header})
            assert response.status_code == 200
            assert response.json()["version"] == expected_version

    def test_path_pattern_parsing(self, client):
        """Test various URL path patterns."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        @app.get("/api/v1/users")
        @app.get("/api/v1/data/process")
        async def versioned_endpoint(request: Request):
            return {"version": get_api_version(request)}

        client = TestClient(app)

        # Both paths should parse v1
        response1 = client.get("/api/v1/users")
        assert response1.json()["version"] == "v1"

        response2 = client.get("/api/v1/data/process")
        assert response2.json()["version"] == "v1"

    def test_request_state_populated(self, client):
        """Test middleware populates request.state.api_version."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        captured_state = {}

        @app.get("/test")
        async def test_endpoint(request: Request):
            captured_state["api_version"] = request.state.api_version
            return {"ok": True}

        client = TestClient(app)
        client.get("/test", headers={"Accept": "application/vnd.narrativeml.v1+json"})

        assert captured_state["api_version"] == "v1"

    def test_response_headers_always_present(self, client):
        """Test version headers are always added to responses."""
        response = client.get("/test")

        assert "X-API-Version" in response.headers
        assert "X-API-Current-Version" in response.headers
        assert response.headers["X-API-Current-Version"] == CURRENT_VERSION


@pytest.mark.unit
class TestGetAPIVersion:
    """Test get_api_version helper function."""

    def test_returns_version_from_state(self):
        """Test helper returns version from request state."""
        from starlette.requests import Request
        from starlette.datastructures import State

        # Create mock request with state
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
            "state": {}
        }

        request = Request(scope)
        request.state.api_version = "v1"

        assert get_api_version(request) == "v1"

    def test_returns_default_when_no_state(self):
        """Test helper returns default when state not set."""
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
            "state": {}
        }

        request = Request(scope)

        assert get_api_version(request) == DEFAULT_VERSION


@pytest.mark.unit
class TestVersionConstants:
    """Test version configuration constants."""

    def test_supported_versions_includes_current(self):
        """Test CURRENT_VERSION is in SUPPORTED_VERSIONS."""
        assert CURRENT_VERSION in SUPPORTED_VERSIONS

    def test_default_version_is_supported(self):
        """Test DEFAULT_VERSION is in SUPPORTED_VERSIONS."""
        assert DEFAULT_VERSION in SUPPORTED_VERSIONS

    def test_version_format(self):
        """Test versions follow expected format."""
        for version in SUPPORTED_VERSIONS:
            assert version.startswith("v")
            assert version[1:].isdigit()


@pytest.mark.unit
class TestVersionNegotiation:
    """Test version negotiation priority."""

    def test_url_overrides_header(self):
        """Test URL version takes precedence over Accept header."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        @app.get("/api/v1/test")
        async def endpoint(request: Request):
            return {"version": get_api_version(request)}

        client = TestClient(app)
        response = client.get(
            "/api/v1/test",
            headers={"Accept": "application/vnd.narrativeml.v2+json"}
        )

        # URL version (v1) wins
        assert response.json()["version"] == "v1"

    def test_header_overrides_default(self):
        """Test Accept header takes precedence over default."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        @app.get("/test")
        async def endpoint(request: Request):
            return {"version": get_api_version(request)}

        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"Accept": "application/vnd.narrativeml.v1+json"}
        )

        # Header version (v1) wins over default
        assert response.json()["version"] == "v1"


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling in version middleware."""

    def test_malformed_version_pattern(self):
        """Test malformed version patterns default gracefully."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        @app.get("/test")
        async def endpoint(request: Request):
            return {"version": get_api_version(request)}

        client = TestClient(app)

        # Malformed patterns should use default
        response = client.get(
            "/test",
            headers={"Accept": "application/vnd.narrativeml.invalid+json"}
        )

        assert response.status_code == 200
        assert response.json()["version"] == DEFAULT_VERSION

    def test_missing_accept_header(self):
        """Test missing Accept header uses default."""
        app = FastAPI()
        app.add_middleware(APIVersionMiddleware)

        @app.get("/test")
        async def endpoint(request: Request):
            return {"version": get_api_version(request)}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["version"] == DEFAULT_VERSION
