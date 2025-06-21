"""
Tests for model export service
"""
import pytest
import tempfile
import json
import zipfile
from unittest.mock import Mock, AsyncMock, patch
from io import BytesIO

from app.services.model_export import ModelExportService
from app.models.ml_model import MLModel
from app.services.model_storage import ModelStorageService


@pytest.fixture
def mock_model():
    """Create a mock ML model"""
    model = Mock()
    model.model_id = "test_model_123"
    model.name = "Test Model"
    model.version = "v1.0"
    model.algorithm = "random_forest"
    model.problem_type = "binary_classification"
    model.feature_names = ["feature1", "feature2", "feature3"]
    model.target_column = "target"
    model.created_at.isoformat.return_value = "2024-01-01T12:00:00Z"
    model.cv_score = 0.85
    model.test_score = 0.83
    model.n_features = 3
    model.model_path = "models/test_model_123/"
    return model


@pytest.fixture
def mock_trained_model():
    """Create a mock trained scikit-learn model"""
    model = Mock()
    model.__class__.__name__ = "RandomForestClassifier"
    model.__class__.__module__ = "sklearn.ensemble"
    model.predict.return_value = [0, 1, 0]
    model.predict_proba.return_value = [[0.8, 0.2], [0.3, 0.7], [0.9, 0.1]]
    model.feature_importances_ = [0.4, 0.35, 0.25]
    return model


@pytest.fixture
def mock_feature_engineer():
    """Create a mock feature engineer"""
    fe = Mock()
    fe.__class__.__name__ = "StandardScaler"
    fe.__class__.__module__ = "sklearn.preprocessing"
    fe.transform.return_value = [[1.0, 2.0, 3.0]]
    return fe


@pytest.fixture
def export_service():
    """Create export service with mocked dependencies"""
    service = ModelExportService()
    service.model_storage = Mock(spec=ModelStorageService)
    service.s3_service = Mock()
    return service


class TestModelExportService:
    """Test cases for ModelExportService"""
    
    @pytest.mark.asyncio
    async def test_get_export_formats(self, export_service):
        """Test getting available export formats"""
        
        formats = await export_service.get_export_formats()
        
        assert isinstance(formats, list)
        assert len(formats) >= 2  # At least Python and Docker should be available
        
        # Check Python format is always available
        python_format = next((f for f in formats if f["name"] == "Python Code"), None)
        assert python_format is not None
        assert python_format["available"] is True
        assert python_format["extension"] == "py"
        
        # Check Docker format is always available
        docker_format = next((f for f in formats if f["name"] == "Docker Container"), None)
        assert docker_format is not None
        assert docker_format["available"] is True
        assert docker_format["extension"] == "zip"
    
    @pytest.mark.asyncio
    async def test_export_python_code_success(
        self, 
        export_service, 
        mock_model, 
        mock_trained_model, 
        mock_feature_engineer
    ):
        """Test successful Python code export"""
        
        # Mock MLModel.find_one
        with patch('app.services.model_export.MLModel') as mock_ml_model:
            mock_ml_model.find_one = AsyncMock(return_value=mock_model)
            
            # Mock model storage load_model
            export_service.model_storage.load_model = AsyncMock(return_value={
                "model": mock_trained_model,
                "feature_engineer": mock_feature_engineer
            })
            
            code, filename = await export_service.export_python_code(
                model_id="test_model_123",
                user_id="user123",
                include_preprocessing=True
            )
            
            # Verify code generation
            assert isinstance(code, str)
            assert len(code) > 1000  # Should be substantial code
            assert "class ModelInference:" in code
            assert "RandomForestClassifier" in code
            assert "StandardScaler" in code
            assert "feature1" in code
            assert "feature2" in code
            assert "feature3" in code
            
            # Verify filename
            assert filename == "Test Model_v1.0_inference.py"
            
            # Verify model storage was called
            export_service.model_storage.load_model.assert_called_once_with("models/test_model_123/")
    
    @pytest.mark.asyncio
    async def test_export_python_code_without_preprocessing(
        self, 
        export_service, 
        mock_model, 
        mock_trained_model
    ):
        """Test Python code export without preprocessing"""
        
        with patch('app.services.model_export.MLModel') as mock_ml_model:
            mock_ml_model.find_one = AsyncMock(return_value=mock_model)
            
            export_service.model_storage.load_model = AsyncMock(return_value={
                "model": mock_trained_model,
                "feature_engineer": None
            })
            
            code, filename = await export_service.export_python_code(
                model_id="test_model_123",
                user_id="user123",
                include_preprocessing=False
            )
            
            assert isinstance(code, str)
            assert "class ModelInference:" in code
            assert "RandomForestClassifier" in code
            # Should not include feature engineer imports when not available
            assert "feature_engineer_path: str = None" in code
    
    @pytest.mark.asyncio
    async def test_export_python_code_model_not_found(self, export_service):
        """Test Python code export when model is not found"""
        
        with patch('app.services.model_export.MLModel') as mock_ml_model:
            mock_ml_model.find_one = AsyncMock(return_value=None)
            
            with pytest.raises(ValueError, match="Model not found"):
                await export_service.export_python_code(
                    model_id="nonexistent",
                    user_id="user123"
                )
    
    @pytest.mark.asyncio
    async def test_export_docker_container_success(
        self, 
        export_service, 
        mock_model, 
        mock_trained_model, 
        mock_feature_engineer
    ):
        """Test successful Docker container export"""
        
        with patch('app.services.model_export.MLModel') as mock_ml_model:
            mock_ml_model.find_one = AsyncMock(return_value=mock_model)
            
            export_service.model_storage.load_model = AsyncMock(return_value={
                "model": mock_trained_model,
                "feature_engineer": mock_feature_engineer
            })
            
            # Mock the export_python_code method since it's called by export_docker_container
            with patch.object(export_service, 'export_python_code') as mock_export_python:
                mock_export_python.return_value = ("# Python code here", "inference.py")
                
                zip_bytes, filename = await export_service.export_docker_container(
                    model_id="test_model_123",
                    user_id="user123"
                )
                
                # Verify ZIP file creation
                assert isinstance(zip_bytes, bytes)
                assert len(zip_bytes) > 0
                assert filename == "Test_Model_v1.0_docker.zip"
                
                # Verify ZIP contents
                zip_buffer = BytesIO(zip_bytes)
                with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                    files_in_zip = zip_file.namelist()
                    
                    # Check required files are present
                    assert "Dockerfile" in files_in_zip
                    assert "inference.py" in files_in_zip
                    assert "app.py" in files_in_zip
                    assert "requirements.txt" in files_in_zip
                    assert "README.md" in files_in_zip
                    
                    # Check Dockerfile content
                    dockerfile_content = zip_file.read("Dockerfile").decode('utf-8')
                    assert "FROM python:" in dockerfile_content
                    assert "pip install" in dockerfile_content
                    
                    # Check requirements.txt content
                    requirements_content = zip_file.read("requirements.txt").decode('utf-8')
                    assert "fastapi" in requirements_content
                    assert "pandas" in requirements_content
                    assert "scikit-learn" in requirements_content
                    
                    # Check README content
                    readme_content = zip_file.read("README.md").decode('utf-8')
                    assert "Test Model" in readme_content
                    assert "docker build" in readme_content
    
    @pytest.mark.asyncio
    @patch('app.services.model_export.ONNX_AVAILABLE', True)
    async def test_export_model_onnx_success(
        self, 
        export_service, 
        mock_model, 
        mock_trained_model
    ):
        """Test successful ONNX export when ONNX is available"""
        
        with patch('app.services.model_export.MLModel') as mock_ml_model:
            mock_ml_model.find_one = AsyncMock(return_value=mock_model)
            
            export_service.model_storage.load_model = AsyncMock(return_value={
                "model": mock_trained_model,
                "feature_engineer": None
            })
            
            # Mock the entire ONNX conversion flow within the service
            with patch.object(export_service, 'export_model_onnx') as mock_export:
                mock_export.return_value = (b"onnx_model_bytes", "Test Model_v1.0.onnx")
                
                onnx_bytes, filename = await export_service.export_model_onnx(
                    model_id="test_model_123",
                    user_id="user123"
                )
                
                assert onnx_bytes == b"onnx_model_bytes"
                assert filename == "Test Model_v1.0.onnx"
                
                # Verify export was called
                mock_export.assert_called_once_with(
                    model_id="test_model_123",
                    user_id="user123"
                )
    
    @pytest.mark.asyncio
    @patch('app.services.model_export.ONNX_AVAILABLE', False)
    async def test_export_model_onnx_not_available(
        self, 
        export_service, 
        mock_model
    ):
        """Test ONNX export when ONNX is not available"""
        
        with patch('app.services.model_export.MLModel') as mock_ml_model:
            mock_ml_model.find_one.return_value = mock_model
            
            with pytest.raises(ValueError, match="ONNX export requires"):
                await export_service.export_model_onnx(
                    model_id="test_model_123",
                    user_id="user123"
                )
    
    @pytest.mark.asyncio
    async def test_export_model_pmml_success(
        self, 
        export_service, 
        mock_model, 
        mock_trained_model
    ):
        """Test successful PMML export when sklearn2pmml is available"""
        
        with patch('app.services.model_export.MLModel') as mock_ml_model:
            mock_ml_model.find_one = AsyncMock(return_value=mock_model)
            
            export_service.model_storage.load_model = AsyncMock(return_value={
                "model": mock_trained_model,
                "feature_engineer": None
            })
            
            # Mock sklearn2pmml imports and functions
            with patch('builtins.__import__') as mock_import:
                mock_sklearn2pmml = Mock()
                mock_pmml_pipeline = Mock()
                
                def side_effect(name, *args, **kwargs):
                    if name == 'sklearn2pmml':
                        return mock_sklearn2pmml
                    elif name == 'sklearn2pmml.pipeline':
                        return mock_pmml_pipeline
                    else:
                        return __import__(name, *args, **kwargs)
                
                mock_import.side_effect = side_effect
                
                # Mock file operations
                with patch('tempfile.NamedTemporaryFile') as mock_temp_file:
                    mock_temp_file.return_value.__enter__.return_value.name = "/tmp/test.pmml"
                    
                    with patch('builtins.open', create=True) as mock_open:
                        mock_open.return_value.__enter__.return_value.read.return_value = "<PMML>test content</PMML>"
                        
                        with patch('os.unlink'):
                            pmml_content, filename = await export_service.export_model_pmml(
                                model_id="test_model_123",
                                user_id="user123"
                            )
                            
                            assert pmml_content == "<PMML>test content</PMML>"
                            assert filename == "Test Model_v1.0.pmml"
    
    @pytest.mark.asyncio
    async def test_export_model_pmml_not_available(
        self, 
        export_service, 
        mock_model
    ):
        """Test PMML export when sklearn2pmml is not available"""
        
        with patch('app.services.model_export.MLModel') as mock_ml_model:
            mock_ml_model.find_one.return_value = mock_model
            
            # Mock ImportError for sklearn2pmml
            with patch('builtins.__import__', side_effect=ImportError("No module named 'sklearn2pmml'")):
                with pytest.raises(ValueError, match="PMML export requires sklearn2pmml"):
                    await export_service.export_model_pmml(
                        model_id="test_model_123",
                        user_id="user123"
                    )
    
    def test_generate_python_code_structure(self, export_service, mock_model, mock_trained_model):
        """Test the structure of generated Python code"""
        
        code = export_service._generate_python_code(
            model=mock_model,
            trained_model=mock_trained_model,
            feature_engineer=None,
            include_preprocessing=True
        )
        
        # Check imports
        assert "import pandas as pd" in code
        assert "import numpy as np" in code
        assert "import pickle" in code
        assert "from sklearn.ensemble import RandomForestClassifier" in code
        
        # Check class definition
        assert "class ModelInference:" in code
        
        # Check methods
        assert "def __init__(self" in code
        assert "def predict(self" in code
        assert "def predict_single(self" in code
        assert "def get_feature_importance(self" in code
        assert "def validate_input(self" in code
        
        # Check feature names inclusion
        for feature in mock_model.feature_names:
            assert feature in code
        
        # Check metadata inclusion
        assert mock_model.name in code
        assert mock_model.version in code
        assert mock_model.algorithm in code
        assert mock_model.target_column in code
        
        # Check example usage
        assert "if __name__ == \"__main__\":" in code
        assert "ModelInference(" in code
    
    def test_generate_python_code_with_feature_engineer(
        self, 
        export_service, 
        mock_model, 
        mock_trained_model, 
        mock_feature_engineer
    ):
        """Test Python code generation with feature engineer"""
        
        code = export_service._generate_python_code(
            model=mock_model,
            trained_model=mock_trained_model,
            feature_engineer=mock_feature_engineer,
            include_preprocessing=True
        )
        
        # Check feature engineer imports
        assert "from sklearn.preprocessing import StandardScaler" in code
        
        # Check feature engineer is used in predict method
        assert "self.feature_engineer.transform" in code
        
        # Check feature engineer loading in __init__
        assert "feature_engineer_path" in code
        assert "self.feature_engineer" in code