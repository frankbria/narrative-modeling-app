"""
Model export service for converting trained models to various formats
"""
import os
import tempfile
import pickle
import json
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import zipfile
from io import BytesIO

try:
    import onnx
    import skl2onnx
    from skl2onnx import convert_sklearn
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

from app.models.ml_model import MLModel
from app.services.model_storage import ModelStorageService
from app.services.s3_service import S3Service


class ModelExportService:
    """Service for exporting models to various formats"""
    
    def __init__(self):
        self.model_storage = ModelStorageService()
        self.s3_service = S3Service()
    
    async def export_model_onnx(
        self,
        model_id: str,
        user_id: str
    ) -> Tuple[bytes, str]:
        """Export model to ONNX format"""
        
        if not ONNX_AVAILABLE:
            raise ValueError("ONNX export requires skl2onnx and onnx packages")
        
        # Get model
        model = await MLModel.find_one({
            "model_id": model_id,
            "user_id": user_id
        })
        
        if not model:
            raise ValueError("Model not found")
        
        # Load model artifacts
        model_artifacts = await self.model_storage.load_model(model.model_path)
        trained_model = model_artifacts["model"]
        
        try:
            # Create sample input for ONNX conversion
            import numpy as np
            sample_input = np.zeros((1, model.n_features), dtype=np.float32)
            
            # Convert to ONNX
            onnx_model = convert_sklearn(
                trained_model,
                initial_types=[('input', skl2onnx.common.data_types.FloatTensorType([None, model.n_features]))],
                target_opset=12
            )
            
            # Serialize ONNX model
            onnx_bytes = onnx_model.SerializeToString()
            filename = f"{model.name}_{model.version}.onnx"
            
            return onnx_bytes, filename
            
        except Exception as e:
            raise ValueError(f"Failed to convert model to ONNX: {str(e)}")
    
    async def export_model_pmml(
        self,
        model_id: str,
        user_id: str
    ) -> Tuple[str, str]:
        """Export model to PMML format"""
        
        try:
            from sklearn2pmml import sklearn2pmml
            from sklearn2pmml.pipeline import PMMLPipeline
        except ImportError:
            raise ValueError("PMML export requires sklearn2pmml package")
        
        # Get model
        model = await MLModel.find_one({
            "model_id": model_id,
            "user_id": user_id
        })
        
        if not model:
            raise ValueError("Model not found")
        
        # Load model artifacts
        model_artifacts = await self.model_storage.load_model(model.model_path)
        trained_model = model_artifacts["model"]
        
        try:
            # Create PMML pipeline
            pipeline = PMMLPipeline([
                ("classifier", trained_model)
            ])
            
            # Generate PMML
            with tempfile.NamedTemporaryFile(suffix='.pmml', delete=False) as temp_file:
                sklearn2pmml(pipeline, temp_file.name)
                
                with open(temp_file.name, 'r') as f:
                    pmml_content = f.read()
                
                os.unlink(temp_file.name)
            
            filename = f"{model.name}_{model.version}.pmml"
            return pmml_content, filename
            
        except Exception as e:
            raise ValueError(f"Failed to convert model to PMML: {str(e)}")
    
    async def export_python_code(
        self,
        model_id: str,
        user_id: str,
        include_preprocessing: bool = True
    ) -> Tuple[str, str]:
        """Generate Python code for the model"""
        
        # Get model
        model = await MLModel.find_one({
            "model_id": model_id,
            "user_id": user_id
        })
        
        if not model:
            raise ValueError("Model not found")
        
        # Load model artifacts
        model_artifacts = await self.model_storage.load_model(model.model_path)
        trained_model = model_artifacts["model"]
        feature_engineer = model_artifacts.get("feature_engineer")
        
        # Generate Python code
        code = self._generate_python_code(
            model=model,
            trained_model=trained_model,
            feature_engineer=feature_engineer,
            include_preprocessing=include_preprocessing
        )
        
        filename = f"{model.name}_{model.version}_inference.py"
        return code, filename
    
    def _generate_python_code(
        self,
        model: MLModel,
        trained_model: Any,
        feature_engineer: Any = None,
        include_preprocessing: bool = True
    ) -> str:
        """Generate Python inference code for the model"""
        
        model_class = trained_model.__class__.__name__
        model_module = trained_model.__class__.__module__
        
        # Generate imports
        imports = [
            "import pandas as pd",
            "import numpy as np",
            "import pickle",
            "from typing import List, Dict, Any, Union",
            f"from {model_module} import {model_class}"
        ]
        
        if feature_engineer:
            fe_class = feature_engineer.__class__.__name__
            fe_module = feature_engineer.__class__.__module__
            imports.append(f"from {fe_module} import {fe_class}")
        
        # Model metadata
        metadata = {
            "model_id": model.model_id,
            "name": model.name,
            "version": model.version,
            "algorithm": model.algorithm,
            "problem_type": model.problem_type,
            "feature_names": model.feature_names,
            "target_column": model.target_column,
            "created_at": model.created_at.isoformat(),
            "performance": {
                "cv_score": model.cv_score,
                "test_score": model.test_score
            }
        }
        
        # Generate the main class
        code = f'''"""
Generated inference code for model: {model.name}
Version: {model.version}
Algorithm: {model.algorithm}
Problem Type: {model.problem_type}

Generated on: {datetime.utcnow().isoformat()}
"""

{chr(10).join(imports)}


class ModelInference:
    """
    Inference class for {model.name}
    
    This class provides methods to load the model and make predictions
    on new data using the same preprocessing pipeline used during training.
    """
    
    def __init__(self, model_path: str, feature_engineer_path: str = None):
        """
        Initialize the inference class
        
        Args:
            model_path: Path to the pickled model file
            feature_engineer_path: Path to the feature engineering pipeline (optional)
        """
        self.metadata = {json.dumps(metadata, indent=4)}
        self.feature_names = {model.feature_names}
        self.target_column = "{model.target_column}"
        
        # Load model
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        # Load feature engineer if provided
        self.feature_engineer = None
        if feature_engineer_path:
            with open(feature_engineer_path, 'rb') as f:
                self.feature_engineer = pickle.load(f)
    
    def predict(self, data: Union[Dict[str, Any], List[Dict[str, Any]], pd.DataFrame]) -> Dict[str, Any]:
        """
        Make predictions on input data
        
        Args:
            data: Input data as dict, list of dicts, or pandas DataFrame
            
        Returns:
            Dictionary containing predictions and metadata
        """
        # Convert input to DataFrame
        if isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            raise ValueError("Input data must be dict, list of dicts, or pandas DataFrame")
        
        # Validate features
        missing_features = set(self.feature_names) - set(df.columns)
        if missing_features:
            raise ValueError(f"Missing required features: {{missing_features}}")
        
        # Apply feature engineering if available
        if self.feature_engineer:
            X = self.feature_engineer.transform(df)
        else:
            X = df[self.feature_names]
        
        # Make predictions
        predictions = self.model.predict(X)
        
        # Get probabilities for classification problems
        probabilities = None
        if "{model.problem_type}" in ["binary_classification", "multiclass_classification"]:
            if hasattr(self.model, 'predict_proba'):
                probabilities = self.model.predict_proba(X).tolist()
        
        # Prepare results
        results = {{
            "predictions": predictions.tolist() if hasattr(predictions, 'tolist') else list(predictions),
            "model_version": "{model.version}",
            "model_name": "{model.name}",
            "timestamp": pd.Timestamp.now().isoformat()
        }}
        
        if probabilities:
            results["probabilities"] = probabilities
        
        return results
    
    def predict_single(self, **kwargs) -> Dict[str, Any]:
        """
        Make a prediction on a single sample
        
        Args:
            **kwargs: Feature values as keyword arguments
            
        Returns:
            Prediction result for single sample
        """
        return self.predict(kwargs)
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance if available
        
        Returns:
            Dictionary mapping feature names to importance scores
        """
        if hasattr(self.model, 'feature_importances_'):
            importance = self.model.feature_importances_
            return dict(zip(self.feature_names, importance.tolist()))
        elif hasattr(self.model, 'coef_'):
            # For linear models
            coef = self.model.coef_
            if len(coef.shape) > 1:
                coef = coef[0]  # Take first class for binary classification
            return dict(zip(self.feature_names, abs(coef).tolist()))
        else:
            return {{}}
    
    def validate_input(self, data: Union[Dict, pd.DataFrame]) -> bool:
        """
        Validate input data format and features
        
        Args:
            data: Input data to validate
            
        Returns:
            True if valid, raises ValueError if invalid
        """
        if isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, pd.DataFrame):
            df = data
        else:
            raise ValueError("Data must be dict or DataFrame")
        
        # Check required features
        missing_features = set(self.feature_names) - set(df.columns)
        if missing_features:
            raise ValueError(f"Missing required features: {{missing_features}}")
        
        # Check data types (basic validation)
        for feature in self.feature_names:
            if df[feature].isnull().any():
                raise ValueError(f"Feature '{{feature}}' contains null values")
        
        return True


# Example usage
if __name__ == "__main__":
    # Initialize the model
    inference = ModelInference("model.pkl", "feature_engineer.pkl")
    
    # Example prediction
    sample_data = {{
        {', '.join([f'"{feature}": 0.0' for feature in model.feature_names[:5]])}  # Add your feature values here
    }}
    
    try:
        result = inference.predict(sample_data)
        print("Prediction:", result["predictions"][0])
        if "probabilities" in result:
            print("Probabilities:", result["probabilities"][0])
    except Exception as e:
        print(f"Error making prediction: {{e}}")
    
    # Get feature importance
    importance = inference.get_feature_importance()
    if importance:
        print("\\nTop 5 most important features:")
        sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        for feature, score in sorted_features[:5]:
            print(f"  {{feature}}: {{score:.4f}}")
'''
        
        return code
    
    async def export_docker_container(
        self,
        model_id: str,
        user_id: str
    ) -> Tuple[bytes, str]:
        """Generate a Docker container with the model"""
        
        # Get model
        model = await MLModel.find_one({
            "model_id": model_id,
            "user_id": user_id
        })
        
        if not model:
            raise ValueError("Model not found")
        
        # Generate Python code
        python_code, _ = await self.export_python_code(model_id, user_id)
        
        # Create Dockerfile
        dockerfile_content = f'''FROM python:3.11-slim

# Install required packages
RUN pip install pandas numpy scikit-learn

# Copy model files
COPY model.pkl /app/
COPY feature_engineer.pkl /app/
COPY inference.py /app/

WORKDIR /app

# Install any additional requirements
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Create API endpoint
COPY app.py /app/
EXPOSE 8000

CMD ["python", "app.py"]
'''
        
        # Create FastAPI app
        api_code = f'''"""
FastAPI application for {model.name}
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Union
import uvicorn
from inference import ModelInference

app = FastAPI(title="{model.name} API", version="{model.version}")

# Initialize model
model_inference = ModelInference("model.pkl", "feature_engineer.pkl")

class PredictionRequest(BaseModel):
    data: Union[Dict[str, Any], List[Dict[str, Any]]]

class PredictionResponse(BaseModel):
    predictions: List[Any]
    probabilities: List[List[float]] = None
    model_version: str
    model_name: str
    timestamp: str

@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    try:
        result = model_inference.predict(request.data)
        return PredictionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
async def health():
    return {{"status": "healthy", "model": "{model.name}", "version": "{model.version}"}}

@app.get("/info")
async def model_info():
    return model_inference.metadata

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
        
        # Create requirements.txt
        requirements = '''fastapi==0.104.1
uvicorn==0.24.0
pandas==2.1.3
numpy==1.25.2
scikit-learn==1.3.2
'''
        
        # Create ZIP file with all components
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("Dockerfile", dockerfile_content)
            zip_file.writestr("inference.py", python_code)
            zip_file.writestr("app.py", api_code)
            zip_file.writestr("requirements.txt", requirements)
            
            # Add README
            readme = f'''# {model.name} Docker Container

This container provides a REST API for the {model.name} model.

## Build and Run

```bash
# Build the container
docker build -t {model.name.lower().replace(" ", "-")} .

# Run the container
docker run -p 8000:8000 {model.name.lower().replace(" ", "-")}
```

## API Endpoints

- `POST /predict` - Make predictions
- `GET /health` - Health check
- `GET /info` - Model information

## Example Usage

```python
import requests

# Make a prediction
response = requests.post("http://localhost:8000/predict", json={{
    "data": {{{', '.join([f'"{feature}": 0.0' for feature in model.feature_names[:3]])}}}
}})

print(response.json())
```
'''
            zip_file.writestr("README.md", readme)
        
        zip_buffer.seek(0)
        filename = f"{model.name.replace(' ', '_')}_{model.version}_docker.zip"
        
        return zip_buffer.getvalue(), filename
    
    async def get_export_formats(self) -> List[Dict[str, Any]]:
        """Get available export formats"""
        
        formats = [
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
                "available": ONNX_AVAILABLE
            }
        ]
        
        try:
            import sklearn2pmml
            formats.append({
                "name": "PMML",
                "extension": "pmml",
                "description": "Predictive Model Markup Language",
                "available": True
            })
        except ImportError:
            formats.append({
                "name": "PMML",
                "extension": "pmml", 
                "description": "Predictive Model Markup Language (requires sklearn2pmml)",
                "available": False
            })
        
        return formats