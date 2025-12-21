# API Documentation

## Overview

The Narrative Modeling App backend provides RESTful APIs for dataset management, transformations, AI-powered analysis, and model training.

**Base URL**: `http://localhost:8000/api/v1`
**Production URL**: Contact deployment team for production endpoint

## Authentication

All API endpoints require authentication using NextAuth session tokens or bearer tokens.

### Headers

```
Authorization: Bearer <token>
Content-Type: application/json
```

## Core API Endpoints

### Datasets

- `GET /datasets` - List all datasets for current user
- `POST /datasets/upload` - Upload new dataset
- `GET /datasets/{id}` - Get dataset metadata
- `GET /datasets/{id}/preview` - Preview dataset rows
- `DELETE /datasets/{id}` - Delete dataset
- `GET /datasets/{id}/statistics` - Get dataset statistics

### Transformations

- `GET /transformations/types` - Get available transformation types
- `POST /transformations/preview` - Preview transformation results
- `POST /transformations/apply` - Apply transformation to dataset
- `GET /transformations/datasets/{id}/config` - Get transformation configuration
- `GET /transformations/datasets/{id}/history` - Get transformation history

See [Transformation History Documentation](../../claudedocs/TRANSFORMATION_HISTORY.md) for history API details.

### Recipes

- `GET /recipes` - List transformation recipes
- `POST /recipes` - Create new recipe
- `GET /recipes/{id}` - Get recipe details
- `POST /recipes/{id}/apply` - Apply recipe to dataset
- `GET /recipes/{id}/export` - Export recipe as code

See [Recipe System Documentation](RECIPE_SYSTEM.md) for recipe API details.

### AI Analysis

- `POST /ai/summarize` - Generate AI summary of dataset
- `POST /ai/suggest-transformations` - Get AI transformation suggestions
- `GET /ai/summary/{dataset_id}` - Get cached AI summary

### Model Training

- `POST /models/train` - Train ML model on dataset
- `GET /models/{id}` - Get model details
- `GET /models/{id}/metrics` - Get model performance metrics
- `GET /models/{id}/download` - Download trained model

## Response Formats

### Success Response

```json
{
  "status": "success",
  "data": { ... },
  "message": "Operation completed successfully"
}
```

### Error Response

```json
{
  "detail": "Error message",
  "status_code": 400,
  "error_type": "ValidationError"
}
```

## HTTP Status Codes

- `200 OK` - Request succeeded
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

## Rate Limiting

API requests are rate limited to:
- 100 requests per minute for authenticated users
- 10 requests per minute for unauthenticated requests

## Pagination

List endpoints support pagination using query parameters:

```
?page=1&per_page=20&sort_by=created_at&order=desc
```

## File Uploads

File uploads use multipart/form-data:

```bash
curl -X POST http://localhost:8000/api/v1/datasets/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@dataset.csv" \
  -F "name=My Dataset"
```

**Supported formats**: CSV, Parquet, JSON, Excel (.xlsx)
**Maximum file size**: 100MB (configurable via MAX_FILE_SIZE environment variable)

## Interactive API Documentation

FastAPI provides interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## Related Documentation

- [Transformation History](../../claudedocs/TRANSFORMATION_HISTORY.md) - History and undo/redo API
- [Recipe System](RECIPE_SYSTEM.md) - Recipe management API
- [Versioning System](VERSIONING.md) - Dataset versioning API
- [Test Standards](TEST_STANDARDS.md) - Testing requirements for API endpoints
- [Production Deployment](../../docs/deployment/PRODUCTION_API_GUIDE.md) - Production API setup

## Support

For API issues or questions:
- Check [Test Infrastructure](TEST_INFRASTRUCTURE.md) for testing guidance
- Review [Sprint Documentation](SPRINTS.md) for recent changes
- Submit issues to the GitHub repository
