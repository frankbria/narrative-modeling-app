"""
Unit tests for health check endpoints
Tests Story 7.2: Comprehensive Health Checks
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Test basic health endpoint functionality"""

    def test_health_endpoint_returns_alive(self):
        """Test that /health endpoint returns alive status"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data
        assert "environment" in data
        assert "version" in data


@pytest.mark.asyncio
class TestReadinessChecks:
    """Test readiness check with dependency validation"""

    async def test_all_services_healthy(self):
        """Test readiness endpoint when all services are healthy"""
        with patch("app.api.routes.health.check_mongodb_connection", new_callable=AsyncMock) as mock_mongo:
            with patch("app.api.routes.health.check_s3_access", new_callable=AsyncMock) as mock_s3:
                with patch("app.api.routes.health.check_openai_api", new_callable=AsyncMock) as mock_openai:
                    # Mock all services as healthy
                    mock_mongo.return_value = {
                        "status": "healthy",
                        "latency_ms": 15.5,
                        "database": "test_db"
                    }
                    mock_s3.return_value = {
                        "status": "healthy",
                        "latency_ms": 25.3,
                        "bucket": "test-bucket",
                        "accessible": True
                    }
                    mock_openai.return_value = {
                        "status": "healthy",
                        "latency_ms": 150.2,
                        "api_version": "v1"
                    }

                    response = client.get("/health/ready")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "ready"
                    assert data["checks"]["mongodb"]["status"] == "healthy"
                    assert data["checks"]["s3"]["status"] == "healthy"
                    assert data["checks"]["openai"]["status"] == "healthy"

    async def test_mongodb_unhealthy_returns_degraded(self):
        """Test readiness endpoint when MongoDB is unhealthy"""
        with patch("app.api.routes.health.check_mongodb_connection", new_callable=AsyncMock) as mock_mongo:
            with patch("app.api.routes.health.check_s3_access", new_callable=AsyncMock) as mock_s3:
                with patch("app.api.routes.health.check_openai_api", new_callable=AsyncMock) as mock_openai:
                    # Mock MongoDB as unhealthy
                    mock_mongo.return_value = {
                        "status": "unhealthy",
                        "latency_ms": 5000.0,
                        "error": "Connection timeout"
                    }
                    mock_s3.return_value = {
                        "status": "healthy",
                        "latency_ms": 25.3,
                        "bucket": "test-bucket",
                        "accessible": True
                    }
                    mock_openai.return_value = {
                        "status": "healthy",
                        "latency_ms": 150.2,
                        "api_version": "v1"
                    }

                    response = client.get("/health/ready")
                    assert response.status_code == 503
                    data = response.json()
                    assert data["status"] == "degraded"
                    assert data["checks"]["mongodb"]["status"] == "unhealthy"
                    assert "error" in data["checks"]["mongodb"]

    async def test_s3_unhealthy_returns_degraded(self):
        """Test readiness endpoint when S3 is unhealthy"""
        with patch("app.api.routes.health.check_mongodb_connection", new_callable=AsyncMock) as mock_mongo:
            with patch("app.api.routes.health.check_s3_access", new_callable=AsyncMock) as mock_s3:
                with patch("app.api.routes.health.check_openai_api", new_callable=AsyncMock) as mock_openai:
                    # Mock S3 as unhealthy
                    mock_mongo.return_value = {
                        "status": "healthy",
                        "latency_ms": 15.5,
                        "database": "test_db"
                    }
                    mock_s3.return_value = {
                        "status": "unhealthy",
                        "latency_ms": 3000.0,
                        "error": "Access denied"
                    }
                    mock_openai.return_value = {
                        "status": "healthy",
                        "latency_ms": 150.2,
                        "api_version": "v1"
                    }

                    response = client.get("/health/ready")
                    assert response.status_code == 503
                    data = response.json()
                    assert data["status"] == "degraded"
                    assert data["checks"]["s3"]["status"] == "unhealthy"

    async def test_openai_not_configured_still_ready(self):
        """Test that app is still ready when OpenAI is not configured"""
        with patch("app.api.routes.health.check_mongodb_connection", new_callable=AsyncMock) as mock_mongo:
            with patch("app.api.routes.health.check_s3_access", new_callable=AsyncMock) as mock_s3:
                with patch("app.api.routes.health.check_openai_api", new_callable=AsyncMock) as mock_openai:
                    # Mock critical services healthy, OpenAI not configured
                    mock_mongo.return_value = {
                        "status": "healthy",
                        "latency_ms": 15.5,
                        "database": "test_db"
                    }
                    mock_s3.return_value = {
                        "status": "healthy",
                        "latency_ms": 25.3,
                        "bucket": "test-bucket",
                        "accessible": True
                    }
                    mock_openai.return_value = {
                        "status": "not_configured",
                        "latency_ms": 0,
                        "message": "OpenAI API key not configured"
                    }

                    response = client.get("/health/ready")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "ready"
                    assert data["checks"]["openai"]["status"] == "not_configured"


@pytest.mark.asyncio
class TestIndividualHealthChecks:
    """Test individual health check functions"""

    async def test_mongodb_check_success(self):
        """Test MongoDB health check when connection succeeds"""
        from app.api.routes.health import check_mongodb_connection

        mock_db = MagicMock()
        mock_db.name = "test_db"
        mock_db.client.admin.command = AsyncMock(return_value={"ok": 1})

        mock_collection = MagicMock()
        mock_collection.database = mock_db

        with patch("app.models.user_data.UserData.get_motor_collection", return_value=mock_collection):
            result = await check_mongodb_connection()

            assert result["status"] == "healthy"
            assert "latency_ms" in result
            assert result["database"] == "test_db"
            assert result["latency_ms"] >= 0

    async def test_mongodb_check_failure(self):
        """Test MongoDB health check when connection fails"""
        from app.api.routes.health import check_mongodb_connection

        with patch("app.models.user_data.UserData.get_motor_collection") as mock_get_collection:
            mock_get_collection.side_effect = Exception("Connection refused")
            result = await check_mongodb_connection()

            assert result["status"] == "unhealthy"
            assert "error" in result
            assert "Connection refused" in result["error"]

    async def test_s3_check_success(self):
        """Test S3 health check when access succeeds"""
        from app.api.routes.health import check_s3_access

        mock_s3_service = MagicMock()
        mock_s3_service.s3_client.list_buckets.return_value = {
            "Buckets": [{"Name": "test-bucket"}]
        }

        with patch("app.api.routes.health.s3_service", mock_s3_service):
            with patch.dict("os.environ", {"AWS_S3_BUCKET_NAME": "test-bucket"}):
                result = await check_s3_access()

                assert result["status"] == "healthy"
                assert result["bucket"] == "test-bucket"
                assert result["accessible"] is True
                assert "latency_ms" in result

    async def test_s3_check_failure(self):
        """Test S3 health check when access fails"""
        from app.api.routes.health import check_s3_access

        mock_s3_service = MagicMock()
        mock_s3_service.s3_client.list_buckets.side_effect = Exception("Access denied")

        with patch("app.api.routes.health.s3_service", mock_s3_service):
            result = await check_s3_access()

            assert result["status"] == "unhealthy"
            assert "error" in result
            assert "Access denied" in result["error"]

    async def test_openai_check_not_configured(self):
        """Test OpenAI health check when API key is not configured"""
        from app.api.routes.health import check_openai_api

        with patch.dict("os.environ", {}, clear=True):
            result = await check_openai_api()

            assert result["status"] == "not_configured"
            assert "message" in result

    async def test_openai_check_success(self):
        """Test OpenAI health check when API responds successfully"""
        from app.api.routes.health import check_openai_api

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                result = await check_openai_api()

                assert result["status"] == "healthy"
                assert "latency_ms" in result
                assert result["api_version"] == "v1"

    async def test_openai_check_api_error(self):
        """Test OpenAI health check when API returns error"""
        from app.api.routes.health import check_openai_api

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.dict("os.environ", {"OPENAI_API_KEY": "invalid-key"}):
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                result = await check_openai_api()

                assert result["status"] == "unhealthy"
                assert "error" in result
                assert "401" in result["error"]


@pytest.mark.asyncio
class TestParallelExecution:
    """Test that health checks execute in parallel"""

    async def test_parallel_execution_performance(self):
        """Test that health checks run concurrently for better performance"""
        import time
        from app.api.routes.health import check_mongodb_connection, check_s3_access, check_openai_api

        # Mock functions with artificial delay
        async def slow_mongo_check():
            await asyncio.sleep(0.1)  # 100ms delay
            return {"status": "healthy", "latency_ms": 100}

        async def slow_s3_check():
            await asyncio.sleep(0.1)  # 100ms delay
            return {"status": "healthy", "latency_ms": 100}

        async def slow_openai_check():
            await asyncio.sleep(0.1)  # 100ms delay
            return {"status": "healthy", "latency_ms": 100}

        with patch("app.api.routes.health.check_mongodb_connection", side_effect=slow_mongo_check):
            with patch("app.api.routes.health.check_s3_access", side_effect=slow_s3_check):
                with patch("app.api.routes.health.check_openai_api", side_effect=slow_openai_check):
                    start = time.time()
                    response = client.get("/health/ready")
                    duration = time.time() - start

                    # If executed sequentially: ~300ms
                    # If executed in parallel: ~100ms
                    # Allow some overhead, but should be < 200ms if parallel
                    assert duration < 0.2, f"Health checks took {duration}s, expected parallel execution"
                    assert response.status_code == 200
