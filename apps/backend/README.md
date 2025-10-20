# Backend API - Narrative Modeling App

FastAPI-based backend service for the Narrative Modeling Application, providing AI-guided machine learning capabilities through a RESTful API.

## 🏗️ Architecture

- **Framework**: FastAPI with async/await
- **Database**: MongoDB with Beanie ODM
- **Storage**: AWS S3 for datasets and models
- **AI**: OpenAI GPT-4 for data analysis and insights
- **Authentication**: NextAuth v5 JWT validation
- **Caching**: Redis for background tasks and caching

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- uv (Python package manager)
- MongoDB (local or Atlas)
- Redis (optional, for caching)
- AWS S3 bucket
- OpenAI API key

### Installation

```bash
# Navigate to backend directory
cd apps/backend

# Install dependencies with uv
uv sync

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
```

### Environment Variables

Create a `.env` file with the following:

```bash
# Database
MONGODB_URI=mongodb://localhost:27017/narrative_modeling
# or MongoDB Atlas:
# MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/narrative_modeling

# AWS S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=your-bucket-name

# OpenAI
OPENAI_API_KEY=sk-your-openai-key

# NextAuth
NEXTAUTH_SECRET=your-nextauth-secret-key

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Development
SKIP_AUTH=true  # Skip authentication in development
ENVIRONMENT=development
```

### Running the Server

```bash
# Development mode with auto-reload
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 📚 API Documentation

### Authentication

The API uses NextAuth v5 JWT tokens for authentication. Include the token in the Authorization header:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" http://localhost:8000/api/v1/datasets
```

In development, set `SKIP_AUTH=true` to bypass authentication.

### Key Endpoints

#### Health & Status
- `GET /health` - Health check with service dependencies
- `GET /health/ready` - Readiness check for production

#### Data Management
- `POST /api/v1/datasets/upload` - Upload dataset
- `GET /api/v1/datasets` - List user datasets
- `GET /api/v1/datasets/{id}` - Get dataset details
- `DELETE /api/v1/datasets/{id}` - Delete dataset

#### Data Processing
- `POST /api/v1/datasets/{id}/process` - Process and analyze dataset
- `GET /api/v1/datasets/{id}/summary` - Get dataset summary
- `POST /api/v1/datasets/{id}/transform` - Apply transformations

#### AI Analysis
- `POST /api/v1/ai/analyze` - AI-powered data analysis
- `POST /api/v1/ai/insights` - Generate insights

#### Model Training
- `POST /api/v1/models/train` - Train ML model
- `GET /api/v1/models` - List trained models
- `GET /api/v1/models/{id}` - Get model details

#### Predictions
- `POST /api/v1/models/{id}/predict` - Make predictions
- `POST /api/v1/models/{id}/predict/batch` - Batch predictions

See interactive API documentation at `/docs` for complete details.

## 🧪 Testing

> **📚 For comprehensive testing documentation, see [Testing Guide](/docs/testing/guide.md)**

### Quick Start

```bash
# All tests
PYTHONPATH=. uv run pytest -v

# Unit tests only (fast, no database required)
PYTHONPATH=. uv run pytest -m "not integration" -v

# Integration tests (requires Docker services)
docker-compose -f docker-compose.test.yml up -d
PYTHONPATH=. uv run pytest -m integration -v
docker-compose -f docker-compose.test.yml down -v

# With coverage
PYTHONPATH=. uv run pytest --cov=app --cov-report=term-missing -v
```

### Test Coverage Status

- **Unit Tests**: 190 tests passing (>85% coverage)
- **Integration Tests**: 42 tests passing (~90% coverage)
- **Total Coverage**: >85% overall backend coverage

### Documentation

- **[Testing Guide](/docs/testing/guide.md)** - Comprehensive guide for all test types
- **[Integration Tests](/tests/integration/README.md)** - Integration test setup and usage
- **[Test Infrastructure](/docs/TEST_INFRASTRUCTURE.md)** - Test architecture and patterns

## 🏗️ Project Structure

```
apps/backend/
├── app/
│   ├── api/           # API routes
│   │   └── routes/    # Endpoint definitions
│   ├── auth/          # Authentication logic
│   ├── models/        # Data models (Beanie)
│   ├── services/      # Business logic
│   ├── storage/       # Database & S3 operations
│   ├── security/      # Security utilities
│   ├── processing/    # Data processing
│   └── utils/         # Helper functions
├── tests/             # Test suite
│   ├── test_api/      # API endpoint tests
│   ├── test_security/ # Security tests
│   ├── test_processing/ # Data processing tests
│   └── test_model_training/ # ML tests
├── requirements.txt   # Python dependencies
└── pyproject.toml     # Project configuration
```

## 🔒 Security Features

- JWT token validation with NextAuth v5
- PII detection and masking
- File upload validation and sanitization
- Rate limiting (configurable)
- CORS protection
- Input validation with Pydantic
- SQL injection prevention (MongoDB)

## 🔧 Development

### Code Quality

```bash
# Linting
uv run ruff check app/

# Type checking
uv run mypy app/

# Format code
uv run ruff format app/
```

### Adding New Dependencies

```bash
# Add package
uv add package-name

# Add dev dependency
uv add --dev package-name

# Sync dependencies
uv sync
```

## 🚀 Production Deployment

See `PRODUCTION_DEPLOYMENT.md` in project root for:
- Docker deployment
- Environment configuration
- Monitoring setup
- Scaling strategies

### Production Checklist

- [ ] Set strong `NEXTAUTH_SECRET`
- [ ] Configure production MongoDB URI
- [ ] Set up AWS S3 bucket with proper permissions
- [ ] Configure OpenAI API key with rate limits
- [ ] Set `SKIP_AUTH=false` (authentication enabled)
- [ ] Enable HTTPS/SSL
- [ ] Configure CORS for frontend domain
- [ ] Set up health check monitoring
- [ ] Configure backup strategy

## 📊 Monitoring

### Health Checks

The `/health` endpoint provides:
- MongoDB connectivity status
- S3 accessibility status
- OpenAI API status
- Redis status (if configured)
- Overall system health

### Metrics

Prometheus metrics available at `/metrics` (when configured):
- Request latency
- Request count by endpoint
- Error rates
- Model training duration
- Prediction latency

## 🛠️ Troubleshooting

### Common Issues

**MongoDB Connection Error**
```bash
# Check MongoDB is running
mongosh --host localhost:27017

# Verify MONGODB_URI in .env
```

**S3 Upload Fails**
```bash
# Verify AWS credentials
aws s3 ls s3://your-bucket-name

# Check S3_BUCKET in .env
```

**Tests Fail**
```bash
# Ensure MongoDB is running for integration tests
# Or run unit tests only (see Testing section)
```

## 📝 API Versioning

All endpoints are versioned under `/api/v1/`. Future versions will be available at `/api/v2/`, etc.

Legacy endpoints (without version prefix) redirect to v1 with deprecation warnings.

## 🤝 Contributing

1. Follow Python PEP 8 style guide
2. Add type hints to all functions
3. Write tests for new features
4. Update API documentation
5. Run tests before committing

## 📄 License

See LICENSE file in project root.

## 🔗 Related Documentation

- [Product Requirements](../../PRODUCT_REQUIREMENTS.md)
- [User Stories](../../USER_STORIES.md)
- [Sprint Plan](../../SPRINT_IMPLEMENTATION_PLAN.md)
- [Production Deployment](../../PRODUCTION_DEPLOYMENT.md)
- [Production API Guide](../../PRODUCTION_API_GUIDE.md)
