# Backend Scripts

This directory contains utility scripts for database seeding, migrations, and other backend operations.

## E2E Test Data Seeding

### `seed_e2e_data.py`

Seeds MongoDB with test data required for E2E testing.

**What it does:**
- Creates NextAuth test user compatible with MongoDB adapter schema
- Optionally seeds sample datasets for testing workflows
- Verifies seeded data integrity

**Usage:**

```bash
# Basic seeding (test user only)
cd apps/backend
uv run python scripts/seed_e2e_data.py

# Clear existing test data before seeding
uv run python scripts/seed_e2e_data.py --clear

# Seed with sample datasets
uv run python scripts/seed_e2e_data.py --with-data

# Clear and seed everything
uv run python scripts/seed_e2e_data.py --clear --with-data
```

**Environment Variables:**

```bash
# MongoDB connection (default: mongodb://localhost:27017/narrative-modeling-test)
export MONGODB_URI="mongodb://localhost:27017/your-test-db"

# Test user credentials (default: test@narrativeml.com)
export TEST_USER_EMAIL="test@example.com"
export TEST_USER_ID="test-user-12345"
```

**Prerequisites:**

1. MongoDB must be running:
   ```bash
   # Local MongoDB
   mongod --dbpath /path/to/data

   # Or Docker
   docker run -d -p 27017:27017 --name mongodb mongo:latest
   ```

2. Python dependencies installed:
   ```bash
   cd apps/backend
   uv sync
   ```

**Integration with E2E Tests:**

The seed script is automatically run by `test-e2e.sh` before starting E2E tests:

```bash
cd apps/frontend
npm run test:e2e:smoke
```

**Database Schema:**

The script creates data compatible with:
- **NextAuth MongoDB Adapter**: `users`, `accounts`, `sessions` collections
- **Backend Models**: `user_data` collection for datasets

**Troubleshooting:**

**MongoDB Connection Failed:**
```
❌ Failed to connect to MongoDB at mongodb://localhost:27017
```
Solution: Ensure MongoDB is running and accessible at the specified URI.

**User Already Exists:**
```
ℹ️  User test@narrativeml.com already exists
```
This is normal - the script will update the existing user. Use `--clear` to start fresh.

**Import Errors:**
```
ModuleNotFoundError: No module named 'pymongo'
```
Solution: Run `uv sync` in the backend directory to install dependencies.
