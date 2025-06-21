"""
Tests for model export API routes
"""
import pytest
import json
import zipfile
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from io import BytesIO

from app.main import app
from app.services.model_export import ModelExportService
from app.auth.nextauth_auth import get_current_user_id


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_user_id():
    """Mock user ID for authentication"""
    return "test_user_123"


@pytest.fixture
def mock_model_id():
    """Mock model ID"""
    return "test_model_456"


@pytest.fixture
def mock_export_formats():
    """Mock export formats response"""
    return [
        {
            "name": "Python Code",
            "extension": "py",
            "description": "Standalone Python inference code",
            "available": True
        },
        {
            "name": "Docker Container",
            "extension": "zip",
            "description": "Complete Docker container with REST API",
            "available": True
        },
        {
            "name": "ONNX",
            "extension": "onnx",
            "description": "Open Neural Network Exchange format",
            "available": False
        },
        {
            "name": "PMML",
            "extension": "pmml",
            "description": "Predictive Model Markup Language",
            "available": False
        }
    ]


@pytest.fixture(autouse=True)
def override_get_current_user_id():
    app.dependency_overrides[get_current_user_id] = lambda: "test_user_123"
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


class TestModelExportRoutes:
    """Test cases for model export API routes"""
    
    @patch('app.api.routes.model_export.export_service')
    def test_get_export_formats_success(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id, 
        mock_export_formats
    ):
        """Test successful retrieval of export formats"""
        
        # Setup mocks
        mock_export_service.get_export_formats = AsyncMock(return_value=mock_export_formats)
        
        # Make request
        response = client.get(f"/api/v1/models/{mock_model_id}/export/formats")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "formats" in data
        assert len(data["formats"]) == 4
        
        # Check Python format
        python_format = next(f for f in data["formats"] if f["name"] == "Python Code")
        assert python_format["available"] is True
        assert python_format["extension"] == "py"
        
        # Verify service was called
        mock_export_service.get_export_formats.assert_called_once()
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_python_code_success(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test successful Python code export"""
        
        # Setup mocks
        python_code = "# Generated Python inference code\nclass ModelInference:\n    pass"
        filename = "test_model_v1.0_inference.py"
        mock_export_service.export_python_code = AsyncMock(return_value=(python_code, filename))
        
        # Make request
        response = client.get(
            f"/api/v1/models/{mock_model_id}/export/python",
            params={"include_preprocessing": True}
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/x-python; charset=utf-8"
        assert f'attachment; filename={filename}' in response.headers["content-disposition"]
        assert response.content.decode('utf-8') == python_code
        
        # Verify service was called with correct parameters
        mock_export_service.export_python_code.assert_called_once_with(
            model_id=mock_model_id,
            user_id=mock_user_id,
            include_preprocessing=True
        )
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_python_code_without_preprocessing(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test Python code export without preprocessing"""
        
        # Setup mocks
        python_code = "# Generated Python inference code without preprocessing"
        filename = "test_model_v1.0_inference.py"
        mock_export_service.export_python_code = AsyncMock(return_value=(python_code, filename))
        
        # Make request
        response = client.get(
            f"/api/v1/models/{mock_model_id}/export/python",
            params={"include_preprocessing": False}
        )
        
        # Verify response
        assert response.status_code == 200
        
        # Verify service was called with correct parameters
        mock_export_service.export_python_code.assert_called_once_with(
            model_id=mock_model_id,
            user_id=mock_user_id,
            include_preprocessing=False
        )
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_python_code_model_not_found(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test Python code export when model is not found"""
        
        # Setup mocks
        mock_export_service.export_python_code = AsyncMock(
            side_effect=ValueError("Model not found")
        )
        
        # Make request
        response = client.get(f"/api/v1/models/{mock_model_id}/export/python")
        
        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "Model not found" in data["detail"]
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_docker_container_success(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test successful Docker container export"""
        
        # Setup mocks
        mock_get_user.return_value = mock_user_id
        
        # Create a mock ZIP file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr("Dockerfile", "FROM python:3.11-slim")
            zip_file.writestr("app.py", "# FastAPI app")
        zip_bytes = zip_buffer.getvalue()
        filename = "test_model_v1.0_docker.zip"
        
        mock_export_service.export_docker_container = AsyncMock(
            return_value=(zip_bytes, filename)
        )
        
        # Make request
        response = client.get(f"/api/v1/models/{mock_model_id}/export/docker")
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert f'attachment; filename={filename}' in response.headers["content-disposition"]
        assert response.content == zip_bytes
        
        # Verify service was called
        mock_export_service.export_docker_container.assert_called_once_with(
            model_id=mock_model_id,
            user_id=mock_user_id
        )
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_onnx_success(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test successful ONNX export"""
        
        # Setup mocks
        mock_get_user.return_value = mock_user_id
        onnx_bytes = b"fake_onnx_model_data"
        filename = "test_model_v1.0.onnx"
        mock_export_service.export_model_onnx = AsyncMock(return_value=(onnx_bytes, filename))
        
        # Make request
        response = client.get(f"/api/v1/models/{mock_model_id}/export/onnx")
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert f'attachment; filename={filename}' in response.headers["content-disposition"]
        assert response.content == onnx_bytes
        
        # Verify service was called
        mock_export_service.export_model_onnx.assert_called_once_with(
            model_id=mock_model_id,
            user_id=mock_user_id
        )
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_onnx_not_available(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test ONNX export when ONNX is not available"""
        
        # Setup mocks
        mock_get_user.return_value = mock_user_id
        mock_export_service.export_model_onnx = AsyncMock(
            side_effect=ValueError("ONNX export requires skl2onnx package")
        )
        
        # Make request
        response = client.get(f"/api/v1/models/{mock_model_id}/export/onnx")
        
        # Verify error response
        assert response.status_code == 400
        data = response.json()
        assert "ONNX export requires" in data["detail"]
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_pmml_success(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test successful PMML export"""
        
        # Setup mocks
        mock_get_user.return_value = mock_user_id
        pmml_content = "<PMML>test model content</PMML>"
        filename = "test_model_v1.0.pmml"
        mock_export_service.export_model_pmml = AsyncMock(return_value=(pmml_content, filename))
        
        # Make request
        response = client.get(f"/api/v1/models/{mock_model_id}/export/pmml")
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        assert f'attachment; filename={filename}' in response.headers["content-disposition"]
        assert response.content.decode('utf-8') == pmml_content
        
        # Verify service was called
        mock_export_service.export_model_pmml.assert_called_once_with(
            model_id=mock_model_id,
            user_id=mock_user_id
        )
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_model_custom_python(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test custom export with Python format"""
        
        # Setup mocks
        python_code = "# Custom Python code"
        filename = "custom_model.py"
        mock_export_service.export_python_code = AsyncMock(return_value=(python_code, filename))
        
        # Make request
        response = client.post(
            f"/api/v1/models/{mock_model_id}/export/python",
            json={"include_preprocessing": False}
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/x-python; charset=utf-8"
        
        # Verify service was called with custom options
        mock_export_service.export_python_code.assert_called_once_with(
            model_id=mock_model_id,
            user_id=mock_user_id,
            include_preprocessing=False
        )
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_model_custom_unsupported_format(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test custom export with unsupported format"""
        
        # Setup mocks
        mock_get_user.return_value = mock_user_id
        
        # Make request with unsupported format
        response = client.post(f"/api/v1/models/{mock_model_id}/export/unsupported")
        
        # Verify error response
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported export format" in data["detail"]
    
    @patch('app.api.routes.model_export.MLModel')
    @patch('app.api.routes.model_export.export_service')
    def test_get_model_export_info_success(
        self, 
        mock_export_service, 
        mock_ml_model, 
        client, 
        mock_user_id, 
        mock_model_id,
        mock_export_formats
    ):
        """Test successful retrieval of model export information"""
        
        # Setup mocks
        mock_get_user.return_value = mock_user_id
        
        # Mock model
        mock_model = Mock()
        mock_model.model_id = mock_model_id
        mock_model.name = "Test Model"
        mock_model.version = "v1.0"
        mock_model.algorithm = "random_forest"
        mock_model.problem_type = "binary_classification"
        mock_model.n_features = 10
        mock_ml_model.find_one.return_value = mock_model
        
        mock_export_service.get_export_formats = AsyncMock(return_value=mock_export_formats)
        
        # Make request
        response = client.get(f"/api/v1/models/{mock_model_id}/export")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check model information
        assert data["model_id"] == mock_model_id
        assert data["model_name"] == "Test Model"
        assert data["model_version"] == "v1.0"
        assert data["algorithm"] == "random_forest"
        assert data["problem_type"] == "binary_classification"
        assert data["feature_count"] == 10
        
        # Check available formats
        assert "available_formats" in data
        assert len(data["available_formats"]) == 4
        
        # Check export endpoints
        assert "export_endpoints" in data
        endpoints = data["export_endpoints"]
        assert endpoints["python"] == f"/api/v1/models/{mock_model_id}/export/python"
        assert endpoints["docker"] == f"/api/v1/models/{mock_model_id}/export/docker"
        
        # Check usage examples
        assert "usage_examples" in data
        assert "curl_python" in data["usage_examples"]
        assert "curl_docker" in data["usage_examples"]
    
    @patch('app.api.routes.model_export.MLModel')
    def test_get_model_export_info_model_not_found(
        self, 
        mock_ml_model, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test model export info when model is not found"""
        
        # Setup mocks
        mock_get_user.return_value = mock_user_id
        mock_ml_model.find_one.return_value = None
        
        # Make request
        response = client.get(f"/api/v1/models/{mock_model_id}/export")
        
        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "Model not found" in data["detail"]
    
    @patch('app.api.routes.model_export.export_service')
    def test_export_service_internal_error(
        self, 
        mock_export_service, 
        client, 
        mock_user_id, 
        mock_model_id
    ):
        """Test handling of internal service errors"""
        
        # Setup mocks
        mock_get_user.return_value = mock_user_id
        mock_export_service.export_python_code = AsyncMock(
            side_effect=Exception("Internal service error")
        )
        
        # Make request
        response = client.get(f"/api/v1/models/{mock_model_id}/export/python")
        
        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "Export failed" in data["detail"]
        assert "Internal service error" in data["detail"]