"""
API Documentation Service

Provides enhanced OpenAPI documentation, client library generation,
and integration examples for the Narrative Modeling API.
"""
import json
from typing import Optional, Dict, Any
from fastapi import FastAPI
from app.config import settings


class APIDocumentationService:
    """Service for generating comprehensive API documentation"""

    def __init__(self, app: Optional[FastAPI] = None):
        """
        Initialize the documentation service

        Args:
            app: Optional FastAPI application instance
        """
        self.app = app

    def generate_openapi_spec(self) -> Dict[str, Any]:
        """
        Generate enhanced OpenAPI specification

        Returns:
            Enhanced OpenAPI specification dictionary

        Raises:
            ValueError: If no FastAPI app instance is available
        """
        if not self.app:
            raise ValueError("FastAPI app instance required")

        # Get base OpenAPI spec from FastAPI
        base_spec = self.app.openapi()

        # Enhance the spec with additional metadata
        enhanced_spec = self._enhance_openapi_spec(base_spec)

        # Add response examples
        self._add_response_examples(enhanced_spec)

        return enhanced_spec

    def _get_api_description(self) -> str:
        """
        Generate comprehensive API description

        Returns:
            Detailed API description string
        """
        return """
# Narrative Modeling API

A comprehensive AI-guided platform for democratizing Machine Learning, enabling non-expert
analysts to build, explore, and deploy models without writing code.

## Key Features

- **Data Processing**: Upload and process CSV/Excel files with automatic schema detection
- **Automated ML**: Train models with automatic algorithm selection and hyperparameter tuning
- **Model Deployment**: Export trained models as Python scripts, Docker containers, or REST APIs
- **Interactive Analysis**: Explore data with automated visualizations and statistical summaries
- **Production Ready**: Built-in monitoring, circuit breakers, and API versioning

## Authentication

All API endpoints (except health checks) require authentication using either:

- **Bearer Token**: `Authorization: Bearer <your-token>`
- **API Key**: `X-API-Key: <your-api-key>`

## Rate Limits

API endpoints are rate-limited to ensure fair usage:

- **Free Tier**: 100 requests/hour
- **Pro Tier**: 1000 requests/hour
- **Enterprise**: Custom limits

## Versioning

The API uses versioning to ensure backward compatibility. Current version: v1

Specify version using:
- URL path: `/api/v1/endpoint`
- Accept header: `Accept: application/vnd.narrativeml.v1+json`

## Support

For API support and questions, please visit our documentation at https://docs.narrativeml.com
or contact support@narrativeml.com
"""

    def _enhance_openapi_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance OpenAPI spec with additional metadata

        Args:
            spec: Base OpenAPI specification

        Returns:
            Enhanced specification with additional metadata
        """
        # Add comprehensive description
        spec["info"]["description"] = self._get_api_description()

        # Add contact information
        spec["info"]["contact"] = {
            "name": "Narrative Modeling Support",
            "email": "support@narrativeml.com",
            "url": "https://docs.narrativeml.com"
        }

        # Add license information
        spec["info"]["license"] = {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }

        # Add external documentation
        spec["externalDocs"] = {
            "description": "Complete API Documentation",
            "url": "https://docs.narrativeml.com/api"
        }

        # Add servers
        spec["servers"] = [
            {
                "url": getattr(settings, 'API_BASE_URL', 'https://api.narrativeml.com'),
                "description": "Production server"
            },
            {
                "url": "http://localhost:8000",
                "description": "Development server"
            }
        ]

        # Add security schemes
        if "components" not in spec:
            spec["components"] = {}

        spec["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token obtained from authentication endpoint"
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for service-to-service authentication"
            }
        }

        # Add global security requirement
        spec["security"] = [
            {"BearerAuth": []},
            {"ApiKeyAuth": []}
        ]

        # Add common tags with descriptions
        spec["tags"] = [
            {
                "name": "upload",
                "description": "Data upload and file management endpoints"
            },
            {
                "name": "models",
                "description": "Model training, evaluation, and management"
            },
            {
                "name": "predictions",
                "description": "Make predictions using trained models"
            },
            {
                "name": "transformations",
                "description": "Data transformation and feature engineering"
            },
            {
                "name": "export",
                "description": "Export models in various formats"
            },
            {
                "name": "monitoring",
                "description": "Health checks and system monitoring"
            }
        ]

        return spec

    def _add_response_examples(self, spec: Dict[str, Any]) -> None:
        """
        Add example responses to schema definitions

        Args:
            spec: OpenAPI specification to enhance
        """
        if "components" not in spec or "schemas" not in spec["components"]:
            return

        schemas = spec["components"]["schemas"]

        # Add example for prediction response
        if "PredictionResponse" in schemas:
            schemas["PredictionResponse"]["example"] = {
                "predictions": [0.85, 0.92, 0.78],
                "model_id": "model_123",
                "timestamp": "2025-01-15T10:30:00Z",
                "confidence_scores": [0.91, 0.88, 0.84]
            }

        # Add example for model metadata
        if "ModelMetadata" in schemas:
            schemas["ModelMetadata"]["example"] = {
                "model_id": "model_123",
                "algorithm": "random_forest",
                "accuracy": 0.92,
                "created_at": "2025-01-15T08:00:00Z",
                "training_time_seconds": 45.2,
                "feature_count": 12
            }

        # Add example for error response
        if "ErrorResponse" in schemas:
            schemas["ErrorResponse"]["example"] = {
                "error": "Validation Error",
                "detail": "Invalid file format. Please upload CSV or Excel files.",
                "status_code": 400
            }

    def generate_client_libraries(self) -> Dict[str, str]:
        """
        Generate client library code examples

        Returns:
            Dictionary mapping language to client code
        """
        return {
            "python": self._generate_python_client(),
            "javascript": self._generate_javascript_client(),
            "curl": self._generate_curl_examples()
        }

    def _generate_python_client(self) -> str:
        """
        Generate Python client library code

        Returns:
            Python client library as string
        """
        return '''"""
Narrative Modeling API Python Client

Installation:
    pip install requests

Usage:
    from narrative_client import NarrativeModelingClient

    client = NarrativeModelingClient(api_key="your-api-key")
    result = client.upload_data("data.csv")
"""
import requests
from typing import Dict, Any, Optional, List


class NarrativeModelingClient:
    """Python client for Narrative Modeling API"""

    def __init__(self, api_key: str, base_url: str = "https://api.narrativeml.com"):
        """
        Initialize the client

        Args:
            api_key: Your API key
            base_url: Base URL for the API (default: production)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def upload_data(self, file_path: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload a dataset file

        Args:
            file_path: Path to CSV or Excel file
            name: Optional dataset name

        Returns:
            Upload response with dataset ID and metadata
        """
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'name': name} if name else {}
            response = self.session.post(
                f"{self.base_url}/api/v1/upload/file",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()

    def train_model(self, dataset_id: str, target_column: str, algorithm: Optional[str] = None) -> Dict[str, Any]:
        """
        Train a machine learning model

        Args:
            dataset_id: ID of uploaded dataset
            target_column: Name of target column to predict
            algorithm: Optional algorithm (auto-selected if not provided)

        Returns:
            Training response with model ID and metrics
        """
        payload = {
            "dataset_id": dataset_id,
            "target_column": target_column
        }
        if algorithm:
            payload["algorithm"] = algorithm

        response = self.session.post(
            f"{self.base_url}/api/v1/ml/train",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def predict(self, model_id: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Make predictions using a trained model

        Args:
            model_id: ID of trained model
            data: List of input records for prediction

        Returns:
            Predictions with confidence scores
        """
        payload = {
            "model_id": model_id,
            "data": data
        }

        response = self.session.post(
            f"{self.base_url}/api/v1/predictions/predict",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def export_model(self, model_id: str, format: str = "python") -> str:
        """
        Export a trained model

        Args:
            model_id: ID of trained model
            format: Export format (python, docker, api)

        Returns:
            Exported model code or configuration
        """
        response = self.session.get(
            f"{self.base_url}/api/v1/models/{model_id}/export/{format}"
        )
        response.raise_for_status()
        return response.text

    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        Get model metadata and performance metrics

        Args:
            model_id: ID of trained model

        Returns:
            Model metadata including accuracy and feature importance
        """
        response = self.session.get(
            f"{self.base_url}/api/v1/models/{model_id}"
        )
        response.raise_for_status()
        return response.json()


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = NarrativeModelingClient(api_key="your-api-key-here")

    # Upload data
    upload_result = client.upload_data("sales_data.csv", name="Q1 Sales")
    dataset_id = upload_result["dataset_id"]

    # Train model
    train_result = client.train_model(
        dataset_id=dataset_id,
        target_column="revenue"
    )
    model_id = train_result["model_id"]

    # Make predictions
    predictions = client.predict(
        model_id=model_id,
        data=[{"feature1": 10, "feature2": 20}]
    )
    print(f"Predictions: {predictions}")

    # Export model
    python_code = client.export_model(model_id, format="python")
    with open("model.py", "w") as f:
        f.write(python_code)
'''

    def _generate_javascript_client(self) -> str:
        """
        Generate JavaScript client library code

        Returns:
            JavaScript client library as string
        """
        return '''/**
 * Narrative Modeling API JavaScript Client
 *
 * Installation:
 *   npm install axios form-data
 *
 * Usage:
 *   import NarrativeModelingClient from './narrative-client';
 *
 *   const client = new NarrativeModelingClient('your-api-key');
 *   const result = await client.uploadData('data.csv');
 */

// Using fetch API for browser/Node.js compatibility
const fs = require('fs');

class NarrativeModelingClient {
    /**
     * Initialize the client
     * @param {string} apiKey - Your API key
     * @param {string} baseURL - Base URL for the API
     */
    constructor(apiKey, baseURL = 'https://api.narrativeml.com') {
        this.apiKey = apiKey;
        this.baseURL = baseURL;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    async _fetch(url, options = {}) {
        const response = await fetch(this.baseURL + url, {
            ...options,
            headers: {
                ...this.headers,
                ...options.headers
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    }

    /**
     * Upload a dataset file
     * @param {string} filePath - Path to CSV or Excel file
     * @param {string} name - Optional dataset name
     * @returns {Promise<Object>} Upload response
     */
    async uploadData(filePath, name = null) {
        const formData = new FormData();
        formData.append('file', new Blob([fs.readFileSync(filePath)]));
        if (name) {
            formData.append('name', name);
        }

        return this._fetch('/api/v1/upload/file', {
            method: 'POST',
            body: formData
        });
    }

    /**
     * Train a machine learning model
     * @param {string} datasetId - ID of uploaded dataset
     * @param {string} targetColumn - Target column to predict
     * @param {string} algorithm - Optional algorithm
     * @returns {Promise<Object>} Training response
     */
    async trainModel(datasetId, targetColumn, algorithm = null) {
        const payload = {
            dataset_id: datasetId,
            target_column: targetColumn
        };
        if (algorithm) {
            payload.algorithm = algorithm;
        }

        return this._fetch('/api/v1/ml/train', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    /**
     * Make predictions using a trained model
     * @param {string} modelId - ID of trained model
     * @param {Array<Object>} data - Input records
     * @returns {Promise<Object>} Predictions
     */
    async predict(modelId, data) {
        return this._fetch('/api/v1/predictions/predict', {
            method: 'POST',
            body: JSON.stringify({
                model_id: modelId,
                data
            })
        });
    }

    /**
     * Export a trained model
     * @param {string} modelId - ID of trained model
     * @param {string} format - Export format (python, docker, api)
     * @returns {Promise<string>} Exported code
     */
    async exportModel(modelId, format = 'python') {
        const response = await fetch(
            `${this.baseURL}/api/v1/models/${modelId}/export/${format}`,
            { headers: this.headers }
        );
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.text();
    }

    /**
     * Get model metadata
     * @param {string} modelId - ID of trained model
     * @returns {Promise<Object>} Model metadata
     */
    async getModelInfo(modelId) {
        return this._fetch(`/api/v1/models/${modelId}`);
    }
}

// Example usage
const client = new NarrativeModelingClient('your-api-key-here');

(async () => {
    try {
        // Upload data
        const uploadResult = await client.uploadData('sales_data.csv', 'Q1 Sales');
        console.log('Upload successful:', uploadResult.dataset_id);

        // Train model
        const trainResult = await client.trainModel(
            uploadResult.dataset_id,
            'revenue'
        );
        console.log('Training complete:', trainResult.model_id);

        // Make predictions
        const predictions = await client.predict(trainResult.model_id, [
            { feature1: 10, feature2: 20 }
        ]);
        console.log('Predictions:', predictions);

        // Export model
        const pythonCode = await client.exportModel(trainResult.model_id, 'python');
        fs.writeFileSync('model.py', pythonCode);
        console.log('Model exported to model.py');
    } catch (error) {
        console.error('Error:', error.message);
    }
})();

module.exports = NarrativeModelingClient;
'''

    def _generate_curl_examples(self) -> str:
        """
        Generate cURL command examples

        Returns:
            cURL examples as string
        """
        return '''# Narrative Modeling API - cURL Examples

# Set your API key
export API_KEY="your-api-key-here"
export BASE_URL="https://api.narrativeml.com"

# 1. Upload a dataset
curl -X POST "$BASE_URL/api/v1/upload/file" \\
  -H "Authorization: Bearer $API_KEY" \\
  -F "file=@data.csv" \\
  -F "name=My Dataset"

# Response: {"dataset_id": "ds_123", "status": "uploaded"}

# 2. Train a model
curl -X POST "$BASE_URL/api/v1/ml/train" \\
  -H "Authorization: Bearer $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "dataset_id": "ds_123",
    "target_column": "price",
    "algorithm": "random_forest"
  }'

# Response: {"model_id": "model_456", "accuracy": 0.92}

# 3. Make predictions
curl -X POST "$BASE_URL/api/v1/predictions/predict" \\
  -H "Authorization: Bearer $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model_id": "model_456",
    "data": [
      {"bedrooms": 3, "bathrooms": 2, "sqft": 1500}
    ]
  }'

# Response: {"predictions": [350000], "confidence": [0.89]}

# 4. Get model information
curl -X GET "$BASE_URL/api/v1/models/model_456" \\
  -H "Authorization: Bearer $API_KEY"

# 5. Export model as Python script
curl -X GET "$BASE_URL/api/v1/models/model_456/export/python" \\
  -H "Authorization: Bearer $API_KEY" \\
  -o model.py

# 6. Export model as Docker container
curl -X GET "$BASE_URL/api/v1/models/model_456/export/docker" \\
  -H "Authorization: Bearer $API_KEY" \\
  -o Dockerfile

# 7. Health check (no authentication required)
curl -X GET "$BASE_URL/api/v1/health"

# Response: {"status": "healthy", "version": "1.0.0"}
'''

    def generate_integration_examples(self) -> Dict[str, str]:
        """
        Generate integration examples for popular platforms

        Returns:
            Dictionary mapping platform to example code
        """
        return {
            "jupyter": self._generate_jupyter_example(),
            "google_colab": self._generate_colab_example(),
            "streamlit": self._generate_streamlit_example(),
            "flask": self._generate_flask_example()
        }

    def _generate_jupyter_example(self) -> str:
        """Generate Jupyter notebook example"""
        return '''# Narrative Modeling in Jupyter Notebook

import pandas as pd
import requests
import matplotlib.pyplot as plt

class NMClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.narrativeml.com"
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def upload(self, df, name):
        # Save to temp CSV
        df.to_csv("temp.csv", index=False)
        files = {"file": open("temp.csv", "rb")}
        response = requests.post(
            f"{self.base_url}/api/v1/upload/file",
            files=files,
            data={"name": name},
            headers=self.headers
        )
        return response.json()["dataset_id"]

    def train(self, dataset_id, target):
        response = requests.post(
            f"{self.base_url}/api/v1/ml/train",
            json={"dataset_id": dataset_id, "target_column": target},
            headers=self.headers
        )
        return response.json()

# Initialize client
client = NMClient(api_key="your-key")

# Load your data
df = pd.read_csv("your_data.csv")

# Upload and train
dataset_id = client.upload(df, "Analysis Dataset")
result = client.train(dataset_id, target_column="outcome")

# Visualize results
plt.figure(figsize=(10, 6))
plt.bar(result["feature_importance"].keys(),
        result["feature_importance"].values())
plt.title("Feature Importance")
plt.xticks(rotation=45)
plt.show()
'''

    def _generate_colab_example(self) -> str:
        """Generate Google Colab example"""
        return self._generate_jupyter_example()  # Same as Jupyter

    def _generate_streamlit_example(self) -> str:
        """Generate Streamlit app example"""
        return '''# Narrative Modeling Streamlit App

import streamlit as st
import pandas as pd
import requests

st.title("ML Model Builder")

# API configuration
api_key = st.text_input("API Key", type="password")
if not api_key:
    st.stop()

# File upload
uploaded_file = st.file_uploader("Upload CSV", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("Data Preview:", df.head())

    # Column selection
    target_col = st.selectbox("Target Column", df.columns)

    # Train button
    if st.button("Train Model"):
        with st.spinner("Training..."):
            # Upload data
            files = {"file": uploaded_file}
            response = requests.post(
                "https://api.narrativeml.com/api/v1/upload/file",
                files=files,
                headers={"Authorization": f"Bearer {api_key}"}
            )
            dataset_id = response.json()["dataset_id"]

            # Train model
            response = requests.post(
                "https://api.narrativeml.com/api/v1/ml/train",
                json={"dataset_id": dataset_id, "target_column": target_col},
                headers={"Authorization": f"Bearer {api_key}"}
            )
            result = response.json()

            st.success(f"Model trained! Accuracy: {result['accuracy']:.2%}")
            st.write("Model ID:", result["model_id"])
'''

    def _generate_flask_example(self) -> str:
        """Generate Flask integration example"""
        return '''# Narrative Modeling Flask Integration

from flask import Flask, request, jsonify, render_template
import requests

app = Flask(__name__)
API_KEY = "your-api-key"
BASE_URL = "https://api.narrativeml.com"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files['file']
    files = {'file': file}

    response = requests.post(
        f"{BASE_URL}/api/v1/upload/file",
        files=files,
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    return jsonify(response.json())

@app.route('/train', methods=['POST'])
def train_model():
    """Train a model"""
    data = request.json
    response = requests.post(
        f"{BASE_URL}/api/v1/ml/train",
        json=data,
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    return jsonify(response.json())

@app.route('/predict', methods=['POST'])
def predict():
    """Make predictions"""
    data = request.json
    response = requests.post(
        f"{BASE_URL}/api/v1/predictions/predict",
        json=data,
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    return jsonify(response.json())

if __name__ == '__main__':
    app.run(debug=True)
'''

    def generate_postman_collection(self) -> Dict[str, Any]:
        """
        Generate Postman collection for API testing

        Returns:
            Postman collection as dictionary
        """
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
                    "value": "https://api.narrativeml.com",
                    "type": "string"
                },
                {
                    "key": "api_token",
                    "value": "your-api-key-here",
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
                                "url": "{{base_url}}/api/v1/upload/file",
                                "body": {
                                    "mode": "formdata",
                                    "formdata": [
                                        {
                                            "key": "file",
                                            "type": "file",
                                            "src": ""
                                        }
                                    ]
                                }
                            }
                        },
                        {
                            "name": "Get Data Summary",
                            "request": {
                                "method": "GET",
                                "url": "{{base_url}}/api/v1/data/{{dataset_id}}/summary"
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
                                "url": "{{base_url}}/api/v1/ml/train",
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps({
                                        "dataset_id": "{{dataset_id}}",
                                        "target_column": "target"
                                    })
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
                                "url": "{{base_url}}/api/v1/predictions/predict",
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps({
                                        "model_id": "{{model_id}}",
                                        "data": []
                                    })
                                }
                            }
                        }
                    ]
                },
                {
                    "name": "Model Export",
                    "item": [
                        {
                            "name": "Export Python",
                            "request": {
                                "method": "GET",
                                "url": "{{base_url}}/api/v1/models/{{model_id}}/export/python"
                            }
                        }
                    ]
                }
            ]
        }
