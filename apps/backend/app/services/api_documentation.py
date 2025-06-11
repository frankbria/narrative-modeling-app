"""
API documentation service for generating comprehensive API docs
"""
import json
from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from datetime import datetime

from app.config import settings


class APIDocumentationService:
    """Service for generating and managing API documentation"""
    
    def __init__(self, app: FastAPI = None):
        self.app = app
    
    def generate_openapi_spec(self) -> Dict[str, Any]:
        """Generate enhanced OpenAPI specification"""
        
        if not self.app:
            raise ValueError("FastAPI app instance required")
        
        # Get base OpenAPI spec
        openapi_spec = get_openapi(
            title=settings.PROJECT_NAME,
            version="1.0.0",
            description=self._get_api_description(),
            routes=self.app.routes,
            servers=[
                {"url": settings.API_BASE_URL, "description": "Production server"},
                {"url": "http://localhost:8000", "description": "Development server"}
            ]
        )
        
        # Enhance with custom information
        openapi_spec = self._enhance_openapi_spec(openapi_spec)
        
        return openapi_spec
    
    def _get_api_description(self) -> str:
        """Get comprehensive API description"""
        
        return """
# Narrative Modeling API

A comprehensive AI-powered machine learning platform that democratizes data science and model building for non-experts.

## Features

### 🔍 Data Processing & Analysis
- **Secure File Upload**: Upload CSV files with automatic PII detection and security scanning
- **Data Quality Assessment**: Automated data quality checks and recommendations
- **Statistical Analysis**: Comprehensive descriptive statistics and data profiling
- **Exploratory Data Analysis**: AI-powered insights and pattern discovery

### 🤖 Machine Learning
- **AutoML Training**: Automated model training with algorithm selection
- **Model Management**: Version control and model lifecycle management
- **Prediction API**: Real-time and batch prediction capabilities
- **Model Export**: Export models in multiple formats (ONNX, PMML, Python code, Docker)

### 📊 Visualization & Insights
- **Interactive Charts**: Dynamic visualizations with Chart.js
- **AI Insights**: Natural language insights about your data and models
- **Performance Metrics**: Model performance tracking and comparison

### 🚀 Production Features
- **A/B Testing**: Statistical experiment framework for model comparison
- **Batch Processing**: Large-scale prediction jobs with progress tracking
- **API Keys**: Secure programmatic access to your models
- **Monitoring**: Real-time performance and usage monitoring

## Authentication

This API uses Clerk authentication. Include your authentication token in the `Authorization` header:

```
Authorization: Bearer <your-token>
```

## Rate Limiting

API requests are rate-limited to ensure fair usage:
- **Authenticated users**: 1000 requests per hour
- **Anonymous users**: 100 requests per hour

## Error Handling

The API returns standard HTTP status codes:
- `200`: Success
- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (missing or invalid authentication)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (resource doesn't exist)
- `422`: Validation Error (invalid request body)
- `429`: Too Many Requests (rate limit exceeded)
- `500`: Internal Server Error

Error responses include detailed messages:

```json
{
  "detail": "Description of the error",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Support

For support and questions:
- Documentation: https://docs.narrativemodeling.ai
- GitHub: https://github.com/your-org/narrative-modeling-app
- Email: support@narrativemodeling.ai
        """
    
    def _enhance_openapi_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance OpenAPI spec with custom metadata"""
        
        # Add contact information
        spec["info"]["contact"] = {
            "name": "Narrative Modeling Support",
            "url": "https://narrativemodeling.ai/support",
            "email": "support@narrativemodeling.ai"
        }
        
        # Add license
        spec["info"]["license"] = {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
        
        # Add external docs
        spec["externalDocs"] = {
            "description": "Complete Documentation",
            "url": "https://docs.narrativemodeling.ai"
        }
        
        # Add security schemes
        if "components" not in spec:
            spec["components"] = {}
        if "securitySchemes" not in spec["components"]:
            spec["components"]["securitySchemes"] = {}
        
        spec["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "Clerk authentication token"
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for programmatic access"
            }
        }
        
        # Add global security
        spec["security"] = [
            {"BearerAuth": []},
            {"ApiKeyAuth": []}
        ]
        
        # Add custom tags with descriptions
        spec["tags"] = [
            {
                "name": "upload",
                "description": "File upload and data ingestion endpoints"
            },
            {
                "name": "data_processing", 
                "description": "Data analysis and quality assessment"
            },
            {
                "name": "ai_analysis",
                "description": "AI-powered data insights and recommendations"
            },
            {
                "name": "model_training",
                "description": "Machine learning model training and management"
            },
            {
                "name": "models",
                "description": "Model lifecycle management and metadata"
            },
            {
                "name": "model-export",
                "description": "Export models in various formats"
            },
            {
                "name": "predictions",
                "description": "Real-time and batch prediction services"
            },
            {
                "name": "batch-prediction",
                "description": "Large-scale batch prediction jobs"
            },
            {
                "name": "ab-testing",
                "description": "A/B testing and experimentation framework"
            },
            {
                "name": "visualizations",
                "description": "Data visualization and chart generation"
            },
            {
                "name": "analytics",
                "description": "Analytics results and statistical summaries"
            },
            {
                "name": "monitoring",
                "description": "System monitoring and health checks"
            },
            {
                "name": "user_data",
                "description": "User data management and metadata"
            }
        ]
        
        # Add response examples for common schemas
        self._add_response_examples(spec)
        
        return spec
    
    def _add_response_examples(self, spec: Dict[str, Any]):
        """Add example responses to schemas"""
        
        if "components" not in spec:
            spec["components"] = {}
        
        if "schemas" not in spec["components"]:
            spec["components"]["schemas"] = {}
        
        # Add common response examples
        examples = {
            "PredictionResponse": {
                "example": {
                    "predictions": [0.85, 0.23, 0.67],
                    "probabilities": [[0.15, 0.85], [0.77, 0.23], [0.33, 0.67]],
                    "model_id": "model_123",
                    "model_version": "v1.0",
                    "timestamp": "2024-01-01T12:00:00Z",
                    "confidence_intervals": [[0.8, 0.9], [0.2, 0.3], [0.6, 0.7]]
                }
            },
            "ModelMetadata": {
                "example": {
                    "model_id": "model_123",
                    "name": "Customer Churn Predictor",
                    "algorithm": "random_forest",
                    "problem_type": "binary_classification",
                    "version": "v1.0",
                    "accuracy": 0.85,
                    "feature_count": 15,
                    "training_samples": 10000,
                    "created_at": "2024-01-01T12:00:00Z"
                }
            },
            "DataQualityReport": {
                "example": {
                    "overall_score": 0.85,
                    "issues": [
                        {
                            "type": "missing_values",
                            "severity": "medium",
                            "columns": ["age", "income"],
                            "percentage": 0.05
                        }
                    ],
                    "recommendations": [
                        "Consider imputing missing values in 'age' column",
                        "Remove outliers in 'income' column"
                    ]
                }
            },
            "ErrorResponse": {
                "example": {
                    "detail": "Model not found",
                    "error_code": "MODEL_NOT_FOUND",
                    "timestamp": "2024-01-01T12:00:00Z",
                    "request_id": "req_123"
                }
            }
        }
        
        # Add examples to schemas
        for schema_name, example_data in examples.items():
            if schema_name in spec["components"]["schemas"]:
                spec["components"]["schemas"][schema_name]["example"] = example_data["example"]
    
    def generate_client_libraries(self) -> Dict[str, str]:
        """Generate client library examples"""
        
        return {
            "python": self._generate_python_client(),
            "javascript": self._generate_javascript_client(),
            "curl": self._generate_curl_examples()
        }
    
    def _generate_python_client(self) -> str:
        """Generate Python client library example"""
        
        return '''
"""
Narrative Modeling API Python Client
"""
import requests
from typing import Dict, Any, List, Optional
import json

class NarrativeModelingClient:
    """Python client for Narrative Modeling API"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.narrativemodeling.ai"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
    
    def upload_data(self, file_path: str) -> Dict[str, Any]:
        """Upload a CSV file for analysis"""
        with open(file_path, 'rb') as f:
            response = self.session.post(
                f"{self.base_url}/api/v1/upload/file",
                files={"file": f}
            )
        return response.json()
    
    def train_model(self, dataset_id: str, target_column: str, 
                   problem_type: str = "auto") -> Dict[str, Any]:
        """Train a machine learning model"""
        data = {
            "dataset_id": dataset_id,
            "target_column": target_column,
            "problem_type": problem_type
        }
        response = self.session.post(
            f"{self.base_url}/api/v1/ml/train",
            json=data
        )
        return response.json()
    
    def predict(self, model_id: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Make predictions with a trained model"""
        payload = {"data": data}
        response = self.session.post(
            f"{self.base_url}/api/v1/models/{model_id}/predict",
            json=payload
        )
        return response.json()
    
    def export_model(self, model_id: str, format_type: str = "python") -> bytes:
        """Export a model in specified format"""
        response = self.session.get(
            f"{self.base_url}/api/v1/models/{model_id}/export/{format_type}"
        )
        return response.content
    
    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get model metadata and information"""
        response = self.session.get(
            f"{self.base_url}/api/v1/models/{model_id}"
        )
        return response.json()

# Example usage
if __name__ == "__main__":
    client = NarrativeModelingClient("your-api-key")
    
    # Upload data
    result = client.upload_data("data.csv")
    dataset_id = result["dataset_id"]
    
    # Train model
    model_result = client.train_model(dataset_id, "target_column")
    model_id = model_result["model_id"]
    
    # Make prediction
    prediction = client.predict(model_id, [{"feature1": 1.0, "feature2": 2.0}])
    print(f"Prediction: {prediction}")
        '''
    
    def _generate_javascript_client(self) -> str:
        """Generate JavaScript client library example"""
        
        return '''
/**
 * Narrative Modeling API JavaScript Client
 */
class NarrativeModelingClient {
    constructor(apiKey, baseUrl = 'https://api.narrativemodeling.ai') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }
    
    async uploadData(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/api/v1/upload/file`, {
            method: 'POST',
            headers: {
                'Authorization': this.headers.Authorization
            },
            body: formData
        });
        
        return response.json();
    }
    
    async trainModel(datasetId, targetColumn, problemType = 'auto') {
        const response = await fetch(`${this.baseUrl}/api/v1/ml/train`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                dataset_id: datasetId,
                target_column: targetColumn,
                problem_type: problemType
            })
        });
        
        return response.json();
    }
    
    async predict(modelId, data) {
        const response = await fetch(`${this.baseUrl}/api/v1/models/${modelId}/predict`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ data })
        });
        
        return response.json();
    }
    
    async exportModel(modelId, formatType = 'python') {
        const response = await fetch(
            `${this.baseUrl}/api/v1/models/${modelId}/export/${formatType}`,
            {
                headers: this.headers
            }
        );
        
        return response.blob();
    }
    
    async getModelInfo(modelId) {
        const response = await fetch(`${this.baseUrl}/api/v1/models/${modelId}`, {
            headers: this.headers
        });
        
        return response.json();
    }
}

// Example usage
const client = new NarrativeModelingClient('your-api-key');

// Upload and train
document.getElementById('file-input').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    const uploadResult = await client.uploadData(file);
    
    const modelResult = await client.trainModel(
        uploadResult.dataset_id, 
        'target_column'
    );
    
    console.log('Model trained:', modelResult);
});
        '''
    
    def _generate_curl_examples(self) -> str:
        """Generate cURL command examples"""
        
        return '''
# Narrative Modeling API cURL Examples

## Authentication
export API_KEY="your-api-key-here"
export BASE_URL="https://api.narrativemodeling.ai"

## Upload Data
curl -X POST "$BASE_URL/api/v1/upload/file" \\
  -H "Authorization: Bearer $API_KEY" \\
  -F "file=@data.csv"

## Train Model
curl -X POST "$BASE_URL/api/v1/ml/train" \\
  -H "Authorization: Bearer $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "dataset_id": "dataset_123",
    "target_column": "target",
    "problem_type": "binary_classification"
  }'

## Make Prediction
curl -X POST "$BASE_URL/api/v1/models/model_123/predict" \\
  -H "Authorization: Bearer $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "data": [
      {"feature1": 1.0, "feature2": 2.0},
      {"feature1": 1.5, "feature2": 2.5}
    ]
  }'

## Export Model (Python Code)
curl -X GET "$BASE_URL/api/v1/models/model_123/export/python" \\
  -H "Authorization: Bearer $API_KEY" \\
  -o model_inference.py

## Export Model (Docker)
curl -X GET "$BASE_URL/api/v1/models/model_123/export/docker" \\
  -H "Authorization: Bearer $API_KEY" \\
  -o model_container.zip

## Get Model Information
curl -X GET "$BASE_URL/api/v1/models/model_123" \\
  -H "Authorization: Bearer $API_KEY"

## Start A/B Test
curl -X POST "$BASE_URL/api/v1/ab-tests" \\
  -H "Authorization: Bearer $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Model Comparison Test",
    "description": "Compare two models",
    "variants": [
      {"name": "Control", "model_id": "model_123", "traffic_percentage": 50},
      {"name": "Treatment", "model_id": "model_456", "traffic_percentage": 50}
    ],
    "primary_metric": "accuracy"
  }'

## Start Batch Prediction Job
curl -X POST "$BASE_URL/api/v1/batch-prediction/jobs" \\
  -H "Authorization: Bearer $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model_id": "model_123",
    "input_data_url": "s3://bucket/input.csv",
    "output_location": "s3://bucket/predictions.csv"
  }'

## Health Check
curl -X GET "$BASE_URL/api/v1/health" \\
  -H "Authorization: Bearer $API_KEY"
        '''
    
    def generate_integration_examples(self) -> Dict[str, str]:
        """Generate integration examples for popular platforms"""
        
        return {
            "jupyter": self._generate_jupyter_example(),
            "google_colab": self._generate_colab_example(),
            "streamlit": self._generate_streamlit_example(),
            "flask": self._generate_flask_example()
        }
    
    def _generate_jupyter_example(self) -> str:
        """Generate Jupyter notebook example"""
        
        return '''
# Narrative Modeling in Jupyter Notebook

## Installation
!pip install requests pandas matplotlib

## Setup
import pandas as pd
import requests
import matplotlib.pyplot as plt

# Initialize client
class NMClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.narrativemodeling.ai"
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    def upload_df(self, df):
        # Save to temp CSV and upload
        df.to_csv("temp.csv", index=False)
        with open("temp.csv", "rb") as f:
            response = requests.post(
                f"{self.base_url}/api/v1/upload/file",
                headers={"Authorization": self.headers["Authorization"]},
                files={"file": f}
            )
        return response.json()

client = NMClient("your-api-key")

## Load and Upload Data
df = pd.read_csv("your_data.csv")
upload_result = client.upload_df(df)
print("Data uploaded:", upload_result["dataset_id"])

## Train Model
train_data = {
    "dataset_id": upload_result["dataset_id"],
    "target_column": "target",
    "problem_type": "binary_classification"
}

train_response = requests.post(
    f"{client.base_url}/api/v1/ml/train",
    headers=client.headers,
    json=train_data
)

model_info = train_response.json()
print("Model trained:", model_info["model_id"])

## Make Predictions
test_data = df.head(5).drop("target", axis=1).to_dict("records")
pred_response = requests.post(
    f"{client.base_url}/api/v1/models/{model_info['model_id']}/predict",
    headers=client.headers,
    json={"data": test_data}
)

predictions = pred_response.json()
print("Predictions:", predictions["predictions"])

## Visualize Results
plt.figure(figsize=(10, 6))
plt.bar(range(len(predictions["predictions"])), predictions["predictions"])
plt.title("Model Predictions")
plt.xlabel("Sample")
plt.ylabel("Prediction")
plt.show()
        '''
    
    def _generate_colab_example(self) -> str:
        """Generate Google Colab example"""
        
        return '''
# Narrative Modeling in Google Colab

## Mount Google Drive (optional)
from google.colab import drive
drive.mount('/content/drive')

## Install required packages
!pip install requests pandas plotly

## Setup and authenticate
import pandas as pd
import requests
import plotly.express as px
from google.colab import files

# API setup
API_KEY = "your-api-key"  # @param {type:"string"}
BASE_URL = "https://api.narrativemodeling.ai"

headers = {"Authorization": f"Bearer {API_KEY}"}

## Upload data from local file
uploaded = files.upload()
filename = list(uploaded.keys())[0]

# Upload to Narrative Modeling
with open(filename, 'rb') as f:
    response = requests.post(
        f"{BASE_URL}/api/v1/upload/file",
        headers={"Authorization": headers["Authorization"]},
        files={"file": f}
    )

upload_result = response.json()
print("✅ Data uploaded successfully!")
print("Dataset ID:", upload_result["dataset_id"])

## Quick data analysis
analysis_response = requests.get(
    f"{BASE_URL}/api/v1/data/{upload_result['dataset_id']}/summary",
    headers=headers
)

summary = analysis_response.json()
print("\\n📊 Data Summary:")
print(f"Rows: {summary['row_count']}")
print(f"Columns: {summary['column_count']}")

## Train model with interactive parameters
target_column = "target"  # @param {type:"string"}
problem_type = "binary_classification"  # @param ["auto", "binary_classification", "multiclass_classification", "regression"]

train_data = {
    "dataset_id": upload_result["dataset_id"],
    "target_column": target_column,
    "problem_type": problem_type
}

print("🔄 Training model...")
train_response = requests.post(
    f"{BASE_URL}/api/v1/ml/train",
    headers=headers,
    json=train_data
)

model_result = train_response.json()
print("✅ Model trained successfully!")
print("Model ID:", model_result["model_id"])
print("Accuracy:", model_result.get("accuracy", "N/A"))

## Interactive visualization
df = pd.read_csv(filename)
fig = px.histogram(df, x=target_column, title="Target Distribution")
fig.show()
        '''
    
    def _generate_streamlit_example(self) -> str:
        """Generate Streamlit app example"""
        
        return '''
# Streamlit App with Narrative Modeling API

import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import time

# Page config
st.set_page_config(
    page_title="ML Model Builder",
    page_icon="🤖",
    layout="wide"
)

# Title
st.title("🤖 AI-Powered Model Builder")
st.markdown("Build machine learning models without coding!")

# Sidebar for API key
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("API Key", type="password")
    
    if not api_key:
        st.warning("Please enter your API key")
        st.stop()

# Initialize client
headers = {"Authorization": f"Bearer {api_key}"}
base_url = "https://api.narrativemodeling.ai"

# File upload
st.header("📁 Upload Your Data")
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file:
    # Show preview
    df = pd.read_csv(uploaded_file)
    st.subheader("Data Preview")
    st.dataframe(df.head())
    
    # Upload to API
    if st.button("🚀 Upload to Platform"):
        with st.spinner("Uploading..."):
            files = {"file": uploaded_file.getvalue()}
            response = requests.post(
                f"{base_url}/api/v1/upload/file",
                headers={"Authorization": headers["Authorization"]},
                files={"file": uploaded_file}
            )
            
            if response.ok:
                upload_result = response.json()
                st.session_state["dataset_id"] = upload_result["dataset_id"]
                st.success("✅ Data uploaded successfully!")
            else:
                st.error("❌ Upload failed")

# Model training
if "dataset_id" in st.session_state:
    st.header("🎯 Train Your Model")
    
    col1, col2 = st.columns(2)
    
    with col1:
        target_column = st.selectbox("Target Column", df.columns)
    
    with col2:
        problem_type = st.selectbox(
            "Problem Type",
            ["auto", "binary_classification", "multiclass_classification", "regression"]
        )
    
    if st.button("🔥 Train Model"):
        with st.spinner("Training model... This may take a few minutes."):
            train_data = {
                "dataset_id": st.session_state["dataset_id"],
                "target_column": target_column,
                "problem_type": problem_type
            }
            
            response = requests.post(
                f"{base_url}/api/v1/ml/train",
                headers=headers,
                json=train_data
            )
            
            if response.ok:
                model_result = response.json()
                st.session_state["model_id"] = model_result["model_id"]
                st.success("✅ Model trained successfully!")
                
                # Show metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Accuracy", f"{model_result.get('accuracy', 0):.3f}")
                with col2:
                    st.metric("Model Type", model_result.get('algorithm', 'Unknown'))
                with col3:
                    st.metric("Features", model_result.get('n_features', 0))

# Predictions
if "model_id" in st.session_state:
    st.header("🔮 Make Predictions")
    
    # Sample prediction
    st.subheader("Single Prediction")
    
    # Create input fields for features
    feature_cols = [col for col in df.columns if col != target_column]
    inputs = {}
    
    cols = st.columns(min(3, len(feature_cols)))
    for i, feature in enumerate(feature_cols):
        with cols[i % 3]:
            inputs[feature] = st.number_input(f"{feature}", value=float(df[feature].mean()))
    
    if st.button("🎯 Predict"):
        pred_response = requests.post(
            f"{base_url}/api/v1/models/{st.session_state['model_id']}/predict",
            headers=headers,
            json={"data": [inputs]}
        )
        
        if pred_response.ok:
            prediction = pred_response.json()
            st.success(f"Prediction: {prediction['predictions'][0]:.3f}")
            
            if "probabilities" in prediction:
                st.info(f"Confidence: {max(prediction['probabilities'][0]):.3f}")

# Model export
if "model_id" in st.session_state:
    st.header("📦 Export Your Model")
    
    export_format = st.selectbox(
        "Export Format",
        ["python", "docker", "onnx", "pmml"]
    )
    
    if st.button("📥 Download Model"):
        response = requests.get(
            f"{base_url}/api/v1/models/{st.session_state['model_id']}/export/{export_format}",
            headers=headers
        )
        
        if response.ok:
            filename = f"model.{export_format}"
            st.download_button(
                "💾 Download",
                response.content,
                filename,
                mime="application/octet-stream"
            )
        '''
    
    def _generate_flask_example(self) -> str:
        """Generate Flask integration example"""
        
        return '''
# Flask App with Narrative Modeling API

from flask import Flask, request, render_template, jsonify, send_file
import requests
import pandas as pd
import os
import tempfile

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Configuration
API_KEY = os.getenv('NARRATIVE_API_KEY')
BASE_URL = 'https://api.narrativemodeling.ai'
headers = {'Authorization': f'Bearer {API_KEY}'}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload CSV file to Narrative Modeling API"""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Upload to Narrative Modeling
        response = requests.post(
            f'{BASE_URL}/api/v1/upload/file',
            headers={'Authorization': headers['Authorization']},
            files={'file': file}
        )
        
        if response.ok:
            result = response.json()
            return jsonify({
                'success': True,
                'dataset_id': result['dataset_id'],
                'message': 'File uploaded successfully'
            })
        else:
            return jsonify({'error': 'Upload failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/train', methods=['POST'])
def train_model():
    """Train a machine learning model"""
    
    data = request.get_json()
    
    try:
        response = requests.post(
            f'{BASE_URL}/api/v1/ml/train',
            headers=headers,
            json=data
        )
        
        if response.ok:
            result = response.json()
            return jsonify({
                'success': True,
                'model_id': result['model_id'],
                'accuracy': result.get('accuracy'),
                'algorithm': result.get('algorithm')
            })
        else:
            return jsonify({'error': 'Training failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/predict', methods=['POST'])
def predict():
    """Make predictions with a trained model"""
    
    data = request.get_json()
    model_id = data.get('model_id')
    input_data = data.get('data')
    
    try:
        response = requests.post(
            f'{BASE_URL}/api/v1/models/{model_id}/predict',
            headers=headers,
            json={'data': input_data}
        )
        
        if response.ok:
            result = response.json()
            return jsonify({
                'success': True,
                'predictions': result['predictions'],
                'probabilities': result.get('probabilities')
            })
        else:
            return jsonify({'error': 'Prediction failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/<model_id>/<format_type>')
def export_model(model_id, format_type):
    """Export a model in specified format"""
    
    try:
        response = requests.get(
            f'{BASE_URL}/api/v1/models/{model_id}/export/{format_type}',
            headers=headers
        )
        
        if response.ok:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file_path = temp_file.name
            
            # Determine filename and mimetype
            if format_type == 'python':
                filename = f'model_{model_id}.py'
                mimetype = 'text/x-python'
            elif format_type == 'docker':
                filename = f'model_{model_id}.zip'
                mimetype = 'application/zip'
            else:
                filename = f'model_{model_id}.{format_type}'
                mimetype = 'application/octet-stream'
            
            return send_file(
                temp_file_path,
                as_attachment=True,
                download_name=filename,
                mimetype=mimetype
            )
        else:
            return jsonify({'error': 'Export failed'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/models')
def list_models():
    """List all user models"""
    
    try:
        response = requests.get(
            f'{BASE_URL}/api/v1/models',
            headers=headers
        )
        
        if response.ok:
            models = response.json()
            return render_template('models.html', models=models)
        else:
            return "Error loading models", 500
            
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/health')
def health_check():
    """Application health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': pd.Timestamp.now().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=True)

# HTML Templates would go in templates/ folder:
# templates/index.html - Main upload and training interface
# templates/models.html - Model listing and management
        '''
    
    def generate_postman_collection(self) -> Dict[str, Any]:
        """Generate Postman collection for API testing"""
        
        return {
            "info": {
                "name": "Narrative Modeling API",
                "description": "Complete API collection for Narrative Modeling platform",
                "version": "1.0.0",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "{{api_token}}",
                        "type": "string"
                    }
                ]
            },
            "variable": [
                {
                    "key": "base_url",
                    "value": "https://api.narrativemodeling.ai",
                    "type": "string"
                },
                {
                    "key": "api_token",
                    "value": "your-api-token-here",
                    "type": "string"
                }
            ],
            "item": [
                {
                    "name": "Data Management",
                    "item": [
                        {
                            "name": "Upload File",
                            "request": {
                                "method": "POST",
                                "header": [],
                                "body": {
                                    "mode": "formdata",
                                    "formdata": [
                                        {
                                            "key": "file",
                                            "type": "file",
                                            "src": ""
                                        }
                                    ]
                                },
                                "url": {
                                    "raw": "{{base_url}}/api/v1/upload/file",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "upload", "file"]
                                }
                            }
                        },
                        {
                            "name": "Get Data Summary",
                            "request": {
                                "method": "GET",
                                "url": {
                                    "raw": "{{base_url}}/api/v1/data/{{dataset_id}}/summary",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "data", "{{dataset_id}}", "summary"]
                                }
                            }
                        }
                    ]
                },
                {
                    "name": "Model Training",
                    "item": [
                        {
                            "name": "Train Model",
                            "request": {
                                "method": "POST",
                                "header": [
                                    {
                                        "key": "Content-Type",
                                        "value": "application/json"
                                    }
                                ],
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps({
                                        "dataset_id": "{{dataset_id}}",
                                        "target_column": "target",
                                        "problem_type": "binary_classification"
                                    }, indent=2)
                                },
                                "url": {
                                    "raw": "{{base_url}}/api/v1/ml/train",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "ml", "train"]
                                }
                            }
                        },
                        {
                            "name": "Get Model Info",
                            "request": {
                                "method": "GET",
                                "url": {
                                    "raw": "{{base_url}}/api/v1/models/{{model_id}}",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "models", "{{model_id}}"]
                                }
                            }
                        }
                    ]
                },
                {
                    "name": "Predictions",
                    "item": [
                        {
                            "name": "Make Prediction",
                            "request": {
                                "method": "POST",
                                "header": [
                                    {
                                        "key": "Content-Type",
                                        "value": "application/json"
                                    }
                                ],
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps({
                                        "data": [
                                            {"feature1": 1.0, "feature2": 2.0}
                                        ]
                                    }, indent=2)
                                },
                                "url": {
                                    "raw": "{{base_url}}/api/v1/models/{{model_id}}/predict",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "models", "{{model_id}}", "predict"]
                                }
                            }
                        },
                        {
                            "name": "Start Batch Job",
                            "request": {
                                "method": "POST",
                                "header": [
                                    {
                                        "key": "Content-Type",
                                        "value": "application/json"
                                    }
                                ],
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps({
                                        "model_id": "{{model_id}}",
                                        "input_data_url": "s3://bucket/input.csv",
                                        "output_location": "s3://bucket/predictions.csv"
                                    }, indent=2)
                                },
                                "url": {
                                    "raw": "{{base_url}}/api/v1/batch-prediction/jobs",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "batch-prediction", "jobs"]
                                }
                            }
                        }
                    ]
                },
                {
                    "name": "Model Export",
                    "item": [
                        {
                            "name": "Export Python Code",
                            "request": {
                                "method": "GET",
                                "url": {
                                    "raw": "{{base_url}}/api/v1/models/{{model_id}}/export/python",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "models", "{{model_id}}", "export", "python"]
                                }
                            }
                        },
                        {
                            "name": "Export Docker Container",
                            "request": {
                                "method": "GET",
                                "url": {
                                    "raw": "{{base_url}}/api/v1/models/{{model_id}}/export/docker",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "models", "{{model_id}}", "export", "docker"]
                                }
                            }
                        }
                    ]
                }
            ]
        }