# API Documentation Service

## Overview

The API Documentation Service provides comprehensive, automated API documentation generation for the Narrative Modeling App backend. It generates OpenAPI specifications, client libraries, integration examples, and Postman collections to streamline API consumption and integration.

## Location

- **Module**: `app/services/api_documentation.py`
- **Tests**: `tests/test_services/test_api_documentation.py`

## Features

### 1. OpenAPI Specification Generation

Generates enhanced OpenAPI 3.0 specifications with:
- Complete endpoint documentation
- Request/response schemas
- Authentication requirements
- Response examples
- Error documentation

```python
from app.services.api_documentation import APIDocumentationService

service = APIDocumentationService(app)
openapi_spec = service.generate_openapi_spec()
```

### 2. Client Library Generation

Generates ready-to-use client libraries in multiple languages:

#### Python Client
```python
client_code = service.generate_client_libraries()["python"]
```

Features:
- Type-annotated methods
- Automatic authentication handling
- Comprehensive error handling
- Full endpoint coverage

#### JavaScript Client
```python
client_code = service.generate_client_libraries()["javascript"]
```

Features:
- Native fetch API usage
- Promise-based interface
- Automatic JSON handling
- Bearer token authentication

#### cURL Examples
```python
curl_examples = service.generate_client_libraries()["curl"]
```

Provides ready-to-use cURL commands for all endpoints.

### 3. Integration Examples

Generates framework-specific integration examples:

#### Jupyter Notebook Integration
```python
examples = service.generate_integration_examples()
jupyter_example = examples["jupyter"]
```

Shows how to use the API within Jupyter notebooks for data analysis workflows.

#### Streamlit Integration
```python
streamlit_example = examples["streamlit"]
```

Demonstrates building interactive dashboards using the API.

#### Flask Integration
```python
flask_example = examples["flask"]
```

Shows backend-to-backend API integration patterns.

### 4. Postman Collection

Generates Postman collection JSON for API testing:

```python
postman_collection = service.generate_postman_collection()
```

Features:
- Complete endpoint coverage
- Environment variables for base URL and auth
- Example requests and responses
- Organized by endpoint groups

## Implementation Details

### Core Components

#### OpenAPI Enhancement
```python
def _enhance_openapi_spec(self, base_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Enhances OpenAPI spec with additional metadata and documentation."""
```

Adds:
- Contact information
- License details
- Server configurations
- Security schemes
- Tags and descriptions

#### Response Examples
```python
def _add_response_examples(self, spec: Dict[str, Any]) -> None:
    """Adds example responses to OpenAPI spec."""
```

Provides realistic example data for all endpoints.

#### Client Generation
```python
def _generate_python_client(self) -> str:
    """Generates Python client library code."""

def _generate_javascript_client(self) -> str:
    """Generates JavaScript client library code."""

def _generate_curl_examples(self) -> str:
    """Generates cURL command examples."""
```

### Authentication Patterns

All generated clients handle JWT bearer token authentication:

**Python**:
```python
self.headers = {"Authorization": f"Bearer {api_key}"}
```

**JavaScript**:
```javascript
headers: { 'Authorization': `Bearer ${this.apiKey}` }
```

**cURL**:
```bash
-H "Authorization: Bearer YOUR_API_KEY"
```

### Error Handling

Generated clients include comprehensive error handling:

```python
if not response.ok:
    raise Exception(f"API error: {response.status} - {await response.text()}")
```

## Testing

### Test Coverage

The service has 100% test coverage with 13 comprehensive tests:

```bash
PYTHONPATH=. uv run pytest tests/test_services/test_api_documentation.py -v
```

### Test Cases

1. **OpenAPI Generation**: Validates spec structure and completeness
2. **Client Libraries**: Tests Python, JavaScript, and cURL generation
3. **Integration Examples**: Validates Jupyter, Streamlit, and Flask examples
4. **Postman Collection**: Verifies collection structure and variables
5. **Error Handling**: Tests behavior without FastAPI app instance

## Usage Examples

### Basic Setup

```python
from fastapi import FastAPI
from app.services.api_documentation import APIDocumentationService

app = FastAPI()
doc_service = APIDocumentationService(app)
```

### Generate All Documentation

```python
# OpenAPI spec
openapi_spec = doc_service.generate_openapi_spec()

# Client libraries
clients = doc_service.generate_client_libraries()
python_client = clients["python"]
js_client = clients["javascript"]
curl_examples = clients["curl"]

# Integration examples
examples = doc_service.generate_integration_examples()

# Postman collection
postman = doc_service.generate_postman_collection()
```

### Save Documentation

```python
import json

# Save OpenAPI spec
with open("openapi.json", "w") as f:
    json.dump(openapi_spec, f, indent=2)

# Save Python client
with open("narrative_ml_client.py", "w") as f:
    f.write(clients["python"])

# Save Postman collection
with open("narrative_ml.postman_collection.json", "w") as f:
    json.dump(postman, f, indent=2)
```

## API Endpoints Documented

The service documents all backend endpoints including:

- **Data Upload**: `/api/v1/upload`
- **Data Processing**: `/api/v1/process`
- **Model Training**: `/api/v1/train`
- **Predictions**: `/api/v1/predict`
- **Transformations**: `/api/v1/transform`
- **Health Checks**: `/health`

## Integration with FastAPI

The service integrates seamlessly with FastAPI's automatic OpenAPI generation:

```python
from app.main import app
from app.services.api_documentation import APIDocumentationService

# Create service with FastAPI app
doc_service = APIDocumentationService(app)

# Enhanced spec includes all FastAPI metadata plus custom additions
enhanced_spec = doc_service.generate_openapi_spec()
```

## Configuration

The service uses application settings from `app.config`:

```python
from app.config import settings

# Service automatically uses:
# - settings.app_name
# - settings.app_version
# - settings.contact_email
# - settings.api_base_url
```

## Future Enhancements

Potential improvements for future iterations:

1. **Additional Languages**: Go, Ruby, PHP client generation
2. **GraphQL Support**: If GraphQL endpoints are added
3. **SDK Publishing**: Automated client library publishing to package registries
4. **Interactive Documentation**: Integration with Swagger UI customizations
5. **API Changelog**: Automated version diff and migration guides

## Dependencies

- `fastapi`: For OpenAPI spec generation
- `app.config`: For application configuration
- Standard library: `json`, `typing`, `Optional`

## Related Documentation

- [Sprint 8 Completion Report](SPRINT_8_COMPLETION.md)
- [Test Infrastructure Guide](TEST_INFRASTRUCTURE.md)
- [API Versioning Documentation](../app/middleware/api_version.py)

## Maintenance Notes

### Updating Client Libraries

When adding new endpoints:

1. FastAPI automatically updates OpenAPI spec
2. Test client generation to ensure new endpoints are included
3. Update integration examples if new patterns are introduced
4. Regenerate Postman collection

### Version Management

The service respects API versioning:
- Client libraries target specific API versions
- Base URLs include version prefix where applicable
- Documentation clearly indicates supported versions

## Support

For issues or questions about the API Documentation Service:
- Review test cases in `tests/test_services/test_api_documentation.py`
- Check FastAPI's OpenAPI documentation
- Consult Sprint 8 implementation notes
