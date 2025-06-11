"""
Tests for API documentation routes
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.main import app


@pytest.fixture
def client():
    """Create test client"""
    # Override auth dependency for testing
    def fake_get_current_user_id():
        return "test_user_123"
    
    from app.api.deps import get_current_user_id
    app.dependency_overrides[get_current_user_id] = fake_get_current_user_id
    
    client = TestClient(app)
    
    yield client
    
    # Clean up
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def mock_openapi_spec():
    """Mock OpenAPI specification"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Narrative Modeling API",
            "version": "1.0.0",
            "description": "AI-powered ML platform"
        },
        "paths": {
            "/test": {
                "get": {
                    "summary": "Test endpoint",
                    "responses": {"200": {"description": "Success"}}
                }
            }
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer"
                }
            }
        }
    }


@pytest.fixture
def mock_client_libraries():
    """Mock client libraries"""
    return {
        "python": "# Python client code here",
        "javascript": "// JavaScript client code here", 
        "curl": "# cURL examples here"
    }


@pytest.fixture
def mock_integration_examples():
    """Mock integration examples"""
    return {
        "jupyter": "# Jupyter notebook example",
        "streamlit": "# Streamlit app example",
        "flask": "# Flask integration example",
        "google_colab": "# Google Colab example"
    }


@pytest.fixture
def mock_postman_collection():
    """Mock Postman collection"""
    return {
        "info": {
            "name": "Narrative Modeling API",
            "version": "1.0.0"
        },
        "item": [
            {
                "name": "Test Request",
                "request": {
                    "method": "GET",
                    "url": "{{base_url}}/test"
                }
            }
        ]
    }


class TestDocumentationRoutes:
    """Test cases for documentation API routes"""
    
    @patch('app.api.routes.documentation.APIDocumentationService')
    def test_get_openapi_spec_success(self, mock_doc_service_class, client, mock_openapi_spec):
        """Test successful OpenAPI spec retrieval"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.generate_openapi_spec.return_value = mock_openapi_spec
        mock_doc_service_class.return_value = mock_service
        
        # Make request
        response = client.get("/api/docs/openapi.json")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["openapi"] == "3.0.0"
        assert data["info"]["title"] == "Narrative Modeling API"
        assert data["info"]["version"] == "1.0.0"
        assert "paths" in data
        assert "components" in data
        
        # Verify service was called with app instance
        mock_doc_service_class.assert_called_once()
        mock_service.generate_openapi_spec.assert_called_once()
    
    def test_get_swagger_ui_success(self, client):
        """Test successful Swagger UI retrieval"""
        
        response = client.get("/api/docs/swagger")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        
        # Check HTML content
        html_content = response.content.decode('utf-8')
        assert "swagger" in html_content.lower()
        assert "cdn.jsdelivr.net" in html_content  # CDN for Swagger resources
    
    def test_get_redoc_ui_success(self, client):
        """Test successful ReDoc UI retrieval"""
        
        response = client.get("/api/docs/redoc")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        
        # Check HTML content
        html_content = response.content.decode('utf-8')
        assert "redoc" in html_content.lower()
        assert "redoc.standalone.js" in html_content
    
    @patch('app.api.routes.documentation.APIDocumentationService')
    def test_get_client_libraries_success(
        self, 
        mock_doc_service_class, 
        client, 
        mock_client_libraries
    ):
        """Test successful client libraries retrieval"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.generate_client_libraries.return_value = mock_client_libraries
        mock_doc_service_class.return_value = mock_service
        
        # Make request
        response = client.get("/api/docs/client-libraries")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "libraries" in data
        assert "installation" in data
        assert "examples_url" in data
        
        # Check libraries
        libraries = data["libraries"]
        assert "python" in libraries
        assert "javascript" in libraries
        assert "curl" in libraries
        
        # Check installation instructions
        installation = data["installation"]
        assert "python" in installation
        assert "pip install" in installation["python"]
        assert "javascript" in installation
        assert "npm install" in installation["javascript"]
        
        # Verify service was called
        mock_service.generate_client_libraries.assert_called_once()
    
    @patch('app.api.routes.documentation.APIDocumentationService')
    def test_get_integration_examples_success(
        self, 
        mock_doc_service_class, 
        client, 
        mock_integration_examples
    ):
        """Test successful integration examples retrieval"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.generate_integration_examples.return_value = mock_integration_examples
        mock_doc_service_class.return_value = mock_service
        
        # Make request
        response = client.get("/api/docs/examples")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "examples" in data
        assert "platforms" in data
        assert "description" in data
        
        # Check examples
        examples = data["examples"]
        assert "jupyter" in examples
        assert "streamlit" in examples
        assert "flask" in examples
        assert "google_colab" in examples
        
        # Check platforms list
        platforms = data["platforms"]
        assert "jupyter" in platforms
        assert "streamlit" in platforms
        
        # Verify service was called
        mock_service.generate_integration_examples.assert_called_once()
    
    @patch('app.api.routes.documentation.APIDocumentationService')
    def test_get_postman_collection_success(
        self, 
        mock_doc_service_class, 
        client, 
        mock_postman_collection
    ):
        """Test successful Postman collection retrieval"""
        
        # Setup mock
        mock_service = Mock()
        mock_service.generate_postman_collection.return_value = mock_postman_collection
        mock_doc_service_class.return_value = mock_service
        
        # Make request
        response = client.get("/api/docs/postman")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "info" in data
        assert "item" in data
        assert data["info"]["name"] == "Narrative Modeling API"
        assert data["info"]["version"] == "1.0.0"
        assert len(data["item"]) == 1
        
        # Verify service was called
        mock_service.generate_postman_collection.assert_called_once()
    
    def test_get_getting_started_guide_success(self, client):
        """Test successful getting started guide retrieval"""
        
        response = client.get("/api/docs/getting-started")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "title" in data
        assert "steps" in data
        assert "next_steps" in data
        assert "resources" in data
        
        # Check title
        assert "Getting Started" in data["title"]
        
        # Check steps
        steps = data["steps"]
        assert len(steps) >= 5
        
        # Verify step structure
        first_step = steps[0]
        assert "step" in first_step
        assert "title" in first_step
        assert "description" in first_step
        assert "code" in first_step
        
        # Check specific steps
        step_titles = [step["title"] for step in steps]
        assert "Authentication" in step_titles
        assert "Upload Data" in step_titles
        assert "Train Model" in step_titles
        assert "Make Predictions" in step_titles
        assert "Export Model" in step_titles
        
        # Check next steps
        next_steps = data["next_steps"]
        assert len(next_steps) > 0
        assert any("A/B testing" in step for step in next_steps)
        
        # Check resources
        resources = data["resources"]
        assert "documentation" in resources
        assert "examples" in resources
        assert "support" in resources
    
    def test_get_api_changelog_success(self, client):
        """Test successful API changelog retrieval"""
        
        response = client.get("/api/docs/changelog")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "current_version" in data
        assert "changelog" in data
        assert "deprecations" in data
        assert "breaking_changes" in data
        assert "upcoming" in data
        
        # Check current version
        assert data["current_version"] == "1.0.0"
        
        # Check changelog entries
        changelog = data["changelog"]
        assert len(changelog) > 0
        
        # Verify changelog entry structure
        latest_entry = changelog[0]
        assert "version" in latest_entry
        assert "date" in latest_entry
        assert "type" in latest_entry
        assert "changes" in latest_entry
        assert latest_entry["version"] == "1.0.0"
        assert latest_entry["type"] == "major"
        
        # Check upcoming features
        upcoming = data["upcoming"]
        assert len(upcoming) > 0
        assert any("ensemble" in feature.lower() for feature in upcoming)
    
    def test_get_api_status_success(self, client):
        """Test successful API status retrieval"""
        
        response = client.get("/api/docs/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "status" in data
        assert "version" in data
        assert "uptime" in data
        assert "response_time" in data
        assert "services" in data
        assert "rate_limits" in data
        assert "regions" in data
        
        # Check status
        assert data["status"] == "operational"
        assert data["version"] == "1.0.0"
        
        # Check services
        services = data["services"]
        assert "api" in services
        assert "database" in services
        assert "ml_training" in services
        
        # Verify service structure
        api_service = services["api"]
        assert "status" in api_service
        assert "response_time" in api_service
        
        # Check rate limits
        rate_limits = data["rate_limits"]
        assert "authenticated" in rate_limits
        assert "anonymous" in rate_limits
        
        # Check regions
        regions = data["regions"]
        assert len(regions) > 0
        region_names = [region["name"] for region in regions]
        assert "US East" in region_names
    
    def test_get_sdk_information_success(self, client):
        """Test successful SDK information retrieval"""
        
        response = client.get("/api/docs/sdk")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "sdks" in data
        assert "tools" in data
        assert "integrations" in data
        
        # Check SDKs
        sdks = data["sdks"]
        assert "python" in sdks
        assert "javascript" in sdks
        assert "r" in sdks
        
        # Verify SDK structure
        python_sdk = sdks["python"]
        assert "name" in python_sdk
        assert "version" in python_sdk
        assert "installation" in python_sdk
        assert "github" in python_sdk
        assert "documentation" in python_sdk
        
        # Check tools
        tools = data["tools"]
        assert "cli" in tools
        assert "jupyter" in tools
        
        # Check integrations
        integrations = data["integrations"]
        assert "streamlit" in integrations
        assert "flask" in integrations