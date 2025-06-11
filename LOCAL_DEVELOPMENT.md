# Local Development Setup

This guide helps you run the Narrative Modeling App locally for development.

## Prerequisites

1. **Docker & Docker Compose** (for MongoDB and S3)
2. **Python 3.11+** with uv
3. **Node.js 18+**
4. **API Keys**:
   - OpenAI API key
   - Clerk authentication keys

## Quick Start

### 1. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2. Install dependencies

```bash
# Backend
cd apps/backend
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Frontend
cd apps/frontend
npm install
```

### 3. Start infrastructure services

```bash
# From project root
./scripts/local-setup.sh
```

This starts:
- MongoDB on `localhost:27017`
- LocalStack (S3) on `localhost:4566`

### 4. Run the application

#### Option A: Using Docker (Recommended for first time)
```bash
docker compose up
```

#### Option B: Run locally (Faster for development)
```bash
# Terminal 1 - Backend
cd apps/backend
source .venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd apps/frontend
npm run dev
```

## Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Development Workflow

### Making Backend Changes
The backend auto-reloads when you save files. Check the terminal for errors.

### Making Frontend Changes
Next.js provides hot module reloading. Changes appear instantly.

### Database Access
```bash
# Connect to MongoDB
docker exec -it narrative-mongodb mongosh -u admin -p localpassword

# Use the database
use narrative_modeling
db.user_data.find()
```

### Local S3 Access
```bash
# List buckets
docker compose exec localstack awslocal s3 ls

# List files in bucket
docker compose exec localstack awslocal s3 ls s3://narrative-modeling-local/
```

## Troubleshooting

### Port Already in Use
```bash
# Find what's using port 3000
lsof -i :3000  # Mac/Linux
netstat -ano | findstr :3000  # Windows

# Kill the process or change the port
```

### MongoDB Connection Failed
```bash
# Check if MongoDB is running
docker compose ps

# Restart MongoDB
docker compose restart mongodb
```

### Clean Restart
```bash
# Stop everything
docker compose down

# Remove volumes (deletes data)
docker compose down -v

# Start fresh
./scripts/local-setup.sh
docker compose up
```

## Environment Variables

### Backend (.env or apps/backend/.env)
```env
MONGODB_URI=mongodb://admin:localpassword@localhost:27017/narrative_modeling?authSource=admin
AWS_ENDPOINT_URL=http://localhost:4566
S3_BUCKET_NAME=narrative-modeling-local
OPENAI_API_KEY=your-key
CLERK_SECRET_KEY=your-key
```

### Frontend (apps/frontend/.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your-key
```

## VS Code Setup

### Recommended Extensions
- Python
- Pylance
- ESLint
- Prettier
- Tailwind CSS IntelliSense

### Debug Configuration
Create `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload"],
      "cwd": "${workspaceFolder}/apps/backend",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/apps/backend"
      }
    }
  ]
}
```

## Testing

```bash
# Backend tests
cd apps/backend
uv run pytest

# Frontend tests
cd apps/frontend
npm test
```

## Next Steps

Once local development is working:
1. Complete Sprint 1 tasks (monitoring, security)
2. Start Sprint 2 (data preparation features)
3. When ready to deploy, use the Terraform setup for AWS

## Deployment Options

### Quick Deploy (Lightsail/VPS)
For testing with small datasets, you could:
1. Use docker-compose on your VPS
2. Add nginx as reverse proxy
3. Use managed MongoDB Atlas
4. Use Cloudflare R2 instead of S3

### Production Deploy (AWS)
When ready for scale:
1. Use the Terraform infrastructure
2. ECS for auto-scaling
3. RDS or MongoDB Atlas
4. CloudFront CDN