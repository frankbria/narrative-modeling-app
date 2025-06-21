"""
Tests for built-in FastAPI documentation endpoints only.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


class TestFastAPIDocumentation:
    def test_openapi_json(self):
        client = TestClient(app)
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    def test_swagger_ui(self):
        client = TestClient(app)
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    def test_redoc_ui(self):
        client = TestClient(app)
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower()