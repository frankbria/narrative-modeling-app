# Production API Guide

## Getting Started with the Narrative Modeling Production API

### 1. Generate an API Key

1. **Via Web UI**:
   - Navigate to Settings → API Keys
   - Click "Create New API Key"
   - Configure rate limits and expiration
   - Copy the generated key (shown only once!)

2. **Via API** (requires authentication):
   ```bash
   curl -X POST https://api.yourapp.com/api/v1/production/api-keys \
     -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Production App",
       "description": "Main production API key",
       "rate_limit": 5000,
       "expires_in_days": 90
     }'
   ```

### 2. Make Predictions

```bash
curl -X POST https://api.yourapp.com/api/v1/production/v1/models/YOUR_MODEL_ID/predict \
  -H "X-API-Key: sk_live_YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      {"feature1": 123, "feature2": "value", "feature3": 45.6},
      {"feature1": 456, "feature2": "other", "feature3": 78.9}
    ],
    "include_probabilities": true,
    "include_metadata": false
  }'
```

**Response**:
```json
{
  "predictions": ["class_a", "class_b"],
  "probabilities": [[0.85, 0.15], [0.32, 0.68]],
  "model_version": "1.0.0",
  "prediction_id": "pred_abc123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 3. Monitor Your Models

**Get Model Metrics**:
```bash
curl -X GET https://api.yourapp.com/api/v1/monitoring/models/YOUR_MODEL_ID/metrics?hours=24 \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

**Check API Key Usage**:
```bash
curl -X GET https://api.yourapp.com/api/v1/monitoring/api-keys/usage \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

### 4. Best Practices

1. **Security**:
   - Never share API keys publicly
   - Rotate keys regularly
   - Use environment variables
   - Set appropriate rate limits

2. **Error Handling**:
   ```python
   import requests
   
   def predict(data):
       response = requests.post(
           f"{API_URL}/v1/models/{MODEL_ID}/predict",
           headers={"X-API-Key": API_KEY},
           json={"data": data}
       )
       
       if response.status_code == 429:
           # Rate limit exceeded
           retry_after = response.headers.get('Retry-After', 60)
           time.sleep(int(retry_after))
           return predict(data)  # Retry
       
       response.raise_for_status()
       return response.json()
   ```

3. **Batch Predictions**:
   - Send multiple records in one request
   - Maximum 1000 records per request
   - Use async processing for large batches

### 5. Rate Limits

- Default: 1000 requests/hour
- Custom limits available
- Rate limit headers included in responses:
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`

### 6. SDK Examples

**Python**:
```python
from narrative_modeling import Client

client = Client(api_key="sk_live_xxx")
model = client.models.get("model_123")

# Single prediction
result = model.predict({"feature1": 123, "feature2": "value"})

# Batch prediction
results = model.predict_batch([
    {"feature1": 123, "feature2": "value"},
    {"feature1": 456, "feature2": "other"}
])
```

**JavaScript**:
```javascript
import { NarrativeModeling } from '@narrative-modeling/sdk';

const client = new NarrativeModeling({ apiKey: 'sk_live_xxx' });
const model = await client.models.get('model_123');

// Single prediction
const result = await model.predict({ feature1: 123, feature2: 'value' });

// Batch prediction
const results = await model.predictBatch([
  { feature1: 123, feature2: 'value' },
  { feature1: 456, feature2: 'other' }
]);
```

### 7. Monitoring Dashboard

Access the monitoring dashboard at:
- https://app.yourapp.com/monitor

Features:
- Real-time prediction metrics
- Model performance trends
- API key usage statistics
- Drift detection alerts
- Prediction distribution analysis

### 8. Troubleshooting

| Error Code | Description | Solution |
|------------|-------------|----------|
| 401 | Invalid API key | Check key format and validity |
| 403 | No model access | Verify API key has access to model |
| 429 | Rate limit exceeded | Wait and retry, or upgrade limits |
| 500 | Server error | Contact support |

### 9. Support

- Documentation: https://docs.yourapp.com
- API Status: https://status.yourapp.com
- Support: support@yourapp.com

## Example Integration

```python
import os
import requests
from typing import List, Dict, Any

class NarrativeModelingClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('NARRATIVE_MODELING_API_KEY')
        self.base_url = "https://api.yourapp.com/api/v1/production"
        
    def predict(self, model_id: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Make predictions using a deployed model"""
        response = requests.post(
            f"{self.base_url}/v1/models/{model_id}/predict",
            headers={"X-API-Key": self.api_key},
            json={"data": data, "include_probabilities": True}
        )
        response.raise_for_status()
        return response.json()
    
    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get information about a deployed model"""
        response = requests.get(
            f"{self.base_url}/v1/models/{model_id}/info",
            headers={"X-API-Key": self.api_key}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = NarrativeModelingClient()
predictions = client.predict("model_123", [
    {"age": 25, "income": 50000, "category": "A"},
    {"age": 35, "income": 75000, "category": "B"}
])
print(f"Predictions: {predictions['predictions']}")
```