"""
Tests for API documentation service
"""
import pytest
import json
from unittest.mock import Mock, patch
from fastapi import FastAPI

from app.services.api_documentation import APIDocumentationService


@pytest.fixture
def mock_app():
    """Create a mock FastAPI app"""
    app = FastAPI(title="Test API", version="1.0.0")
    
    # Add some mock routes
    @app.get("/test")
    def test_route():
        return {"message": "test"}
    
    @app.post("/users")
    def create_user():
        return {"user": "created"}
    
    return app


@pytest.fixture
def doc_service(mock_app):
    """Create documentation service with mock app"""
    return APIDocumentationService(mock_app)


class TestAPIDocumentationService:
    """Test cases for APIDocumentationService"""
    
    def test_init_without_app(self):
        """Test initialization without FastAPI app"""
        service = APIDocumentationService()
        assert service.app is None
    
    def test_init_with_app(self, mock_app):
        """Test initialization with FastAPI app"""
        service = APIDocumentationService(mock_app)
        assert service.app == mock_app
    
    @patch('app.services.api_documentation.settings')
    def test_generate_openapi_spec_success(self, mock_settings, doc_service):
        """Test successful OpenAPI spec generation"""
        
        # Setup settings mock
        mock_settings.PROJECT_NAME = "Test API"
        mock_settings.API_BASE_URL = "https://api.test.com"
        
        spec = doc_service.generate_openapi_spec()
        
        # Verify basic structure
        assert isinstance(spec, dict)
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        assert "components" in spec
        
        # Verify enhanced information
        assert spec["info"]["title"] == "Test API"
        assert spec["info"]["version"] == "1.0.0"
        assert "contact" in spec["info"]
        assert "license" in spec["info"]
        
        # Verify servers
        assert "servers" in spec
        assert len(spec["servers"]) == 2
        assert spec["servers"][0]["url"] == "https://api.test.com"
        assert spec["servers"][1]["url"] == "http://localhost:8000"
        
        # Verify security schemes
        assert "securitySchemes" in spec["components"]
        assert "BearerAuth" in spec["components"]["securitySchemes"]
        assert "ApiKeyAuth" in spec["components"]["securitySchemes"]
        
        # Verify global security
        assert "security" in spec
        assert {"BearerAuth": []} in spec["security"]
        assert {"ApiKeyAuth": []} in spec["security"]
        
        # Verify tags
        assert "tags" in spec
        tag_names = [tag["name"] for tag in spec["tags"]]
        assert "upload" in tag_names
        assert "models" in tag_names
        assert "predictions" in tag_names
    
    def test_generate_openapi_spec_without_app(self):
        """Test OpenAPI spec generation without app raises error"""
        service = APIDocumentationService()
        
        with pytest.raises(ValueError, match="FastAPI app instance required"):
            service.generate_openapi_spec()
    
    def test_get_api_description(self, doc_service):
        """Test API description generation"""
        description = doc_service._get_api_description()
        
        assert isinstance(description, str)
        assert len(description) > 500  # Should be comprehensive
        assert "Narrative Modeling API" in description
        assert "Machine Learning" in description
        assert "Data Processing" in description
        assert "Authorization: Bearer" in description
        assert "rate-limited" in description
    
    def test_enhance_openapi_spec(self, doc_service):
        """Test OpenAPI spec enhancement"""
        
        # Basic spec
        base_spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
            "components": {}
        }
        
        enhanced_spec = doc_service._enhance_openapi_spec(base_spec)
        
        # Verify enhancements
        assert "contact" in enhanced_spec["info"]
        assert "license" in enhanced_spec["info"]
        assert "externalDocs" in enhanced_spec
        assert "securitySchemes" in enhanced_spec["components"]
        assert "security" in enhanced_spec
        assert "tags" in enhanced_spec
        
        # Verify contact info
        contact = enhanced_spec["info"]["contact"]
        assert "name" in contact
        assert "email" in contact
        assert "url" in contact
        
        # Verify license
        license_info = enhanced_spec["info"]["license"]
        assert license_info["name"] == "MIT"
        
        # Verify external docs
        assert "description" in enhanced_spec["externalDocs"]
        assert "url" in enhanced_spec["externalDocs"]
    
    def test_add_response_examples(self, doc_service):
        """Test adding response examples to OpenAPI spec"""
        
        spec = {
            "components": {
                "schemas": {
                    "PredictionResponse": {"type": "object"},
                    "ModelMetadata": {"type": "object"},
                    "ErrorResponse": {"type": "object"}
                }
            }
        }
        
        doc_service._add_response_examples(spec)
        
        # Verify examples were added
        schemas = spec["components"]["schemas"]
        assert "example" in schemas["PredictionResponse"]
        assert "example" in schemas["ModelMetadata"]
        assert "example" in schemas["ErrorResponse"]
        
        # Verify example content
        pred_example = schemas["PredictionResponse"]["example"]
        assert "predictions" in pred_example
        assert "model_id" in pred_example
        assert "timestamp" in pred_example
        
        model_example = schemas["ModelMetadata"]["example"]
        assert "model_id" in model_example
        assert "algorithm" in model_example
        assert "accuracy" in model_example
    
    def test_generate_client_libraries(self, doc_service):
        """Test client library generation"""
        
        libraries = doc_service.generate_client_libraries()
        
        assert isinstance(libraries, dict)
        assert "python" in libraries
        assert "javascript" in libraries
        assert "curl" in libraries
        
        # Verify Python client
        python_client = libraries["python"]
        assert "class NarrativeModelingClient" in python_client
        assert "def upload_data" in python_client
        assert "def train_model" in python_client
        assert "def predict" in python_client
        assert "def export_model" in python_client
        
        # Verify JavaScript client
        js_client = libraries["javascript"]
        assert "class NarrativeModelingClient" in js_client
        assert "async uploadData" in js_client
        assert "async trainModel" in js_client
        assert "async predict" in js_client
        
        # Verify cURL examples
        curl_examples = libraries["curl"]
        assert "curl -X POST" in curl_examples
        assert "Authorization: Bearer" in curl_examples
        assert "/api/v1/upload/file" in curl_examples
        assert "/api/v1/ml/train" in curl_examples
    
    def test_generate_python_client(self, doc_service):
        """Test Python client generation"""
        
        python_client = doc_service._generate_python_client()
        
        # Check class definition
        assert "class NarrativeModelingClient:" in python_client
        
        # Check methods
        assert "def __init__(self" in python_client
        assert "def upload_data(self" in python_client
        assert "def train_model(self" in python_client
        assert "def predict(self" in python_client
        assert "def export_model(self" in python_client
        assert "def get_model_info(self" in python_client
        
        # Check imports
        assert "import requests" in python_client
        assert "from typing import" in python_client
        
        # Check example usage
        assert "if __name__ == \"__main__\":" in python_client
        assert "client = NarrativeModelingClient" in python_client
    
    def test_generate_javascript_client(self, doc_service):
        """Test JavaScript client generation"""
        
        js_client = doc_service._generate_javascript_client()
        
        # Check class definition
        assert "class NarrativeModelingClient" in js_client
        
        # Check methods
        assert "constructor(apiKey" in js_client
        assert "async uploadData(" in js_client
        assert "async trainModel(" in js_client
        assert "async predict(" in js_client
        assert "async exportModel(" in js_client
        
        # Check fetch usage
        assert "fetch(" in js_client
        assert "FormData" in js_client
        assert "JSON.stringify" in js_client
        
        # Check example usage
        assert "const client = new NarrativeModelingClient" in js_client
    
    def test_generate_curl_examples(self, doc_service):
        """Test cURL examples generation"""
        
        curl_examples = doc_service._generate_curl_examples()
        
        # Check environment variables
        assert "export API_KEY=" in curl_examples
        assert "export BASE_URL=" in curl_examples
        
        # Check endpoints
        assert "curl -X POST" in curl_examples
        assert "curl -X GET" in curl_examples
        assert "/api/v1/upload/file" in curl_examples
        assert "/api/v1/ml/train" in curl_examples
        assert "/api/v1/models/" in curl_examples
        assert "/export/python" in curl_examples
        assert "/export/docker" in curl_examples
        
        # Check headers
        assert "Authorization: Bearer $API_KEY" in curl_examples
        assert "Content-Type: application/json" in curl_examples
        
        # Check data
        assert "-d '{" in curl_examples
        assert '"dataset_id":' in curl_examples
        assert '"target_column":' in curl_examples
    
    def test_generate_integration_examples(self, doc_service):
        """Test integration examples generation"""
        
        examples = doc_service.generate_integration_examples()
        
        assert isinstance(examples, dict)
        assert "jupyter" in examples
        assert "google_colab" in examples
        assert "streamlit" in examples
        assert "flask" in examples
        
        # Verify Jupyter example
        jupyter_example = examples["jupyter"]
        assert "import pandas as pd" in jupyter_example
        assert "class NMClient:" in jupyter_example
        assert "plt.figure" in jupyter_example
        
        # Verify Streamlit example
        streamlit_example = examples["streamlit"]
        assert "import streamlit as st" in streamlit_example
        assert "st.title" in streamlit_example
        assert "st.file_uploader" in streamlit_example
        
        # Verify Flask example
        flask_example = examples["flask"]
        assert "from flask import Flask" in flask_example
        assert "@app.route" in flask_example
        assert "def upload_file():" in flask_example
    
    def test_generate_postman_collection(self, doc_service):
        """Test Postman collection generation"""
        
        collection = doc_service.generate_postman_collection()
        
        assert isinstance(collection, dict)
        assert "info" in collection
        assert "auth" in collection
        assert "variable" in collection
        assert "item" in collection
        
        # Verify collection info
        info = collection["info"]
        assert info["name"] == "Narrative Modeling API"
        assert "version" in info
        assert "schema" in info
        
        # Verify authentication
        auth = collection["auth"]
        assert auth["type"] == "bearer"
        
        # Verify variables
        variables = collection["variable"]
        var_keys = [var["key"] for var in variables]
        assert "base_url" in var_keys
        assert "api_token" in var_keys
        
        # Verify request groups
        items = collection["item"]
        group_names = [item["name"] for item in items]
        assert "Data Management" in group_names
        assert "Model Training" in group_names
        assert "Predictions" in group_names
        assert "Model Export" in group_names
        
        # Verify specific requests in groups
        data_management = next(item for item in items if item["name"] == "Data Management")
        request_names = [req["name"] for req in data_management["item"]]
        assert "Upload File" in request_names
        assert "Get Data Summary" in request_names