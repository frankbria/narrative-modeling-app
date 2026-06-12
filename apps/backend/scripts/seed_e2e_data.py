#!/usr/bin/env python3
"""
E2E Test Data Seeding Script

This script seeds the MongoDB database with test data required for E2E testing:
1. NextAuth test user (compatible with NextAuth MongoDB adapter schema)
2. Sample datasets for testing workflows
3. Any other fixtures needed for comprehensive E2E tests

Usage:
    uv run python scripts/seed_e2e_data.py

Environment Variables:
    MONGODB_URI: MongoDB connection string (default: mongodb://localhost:27017)
    MONGODB_DB: MongoDB database name (default: narrative-modeling-test)
    TEST_USER_EMAIL: Test user email (default: test@narrativeml.com)
    TEST_USER_ID: Test user ID (default: test-user-12345)
"""

import os
import sys
from datetime import datetime, UTC
from pymongo import MongoClient

# Configuration from environment variables
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
MONGODB_DB = os.getenv('MONGODB_DB', 'narrative-modeling-test')
TEST_USER_EMAIL = os.getenv('TEST_USER_EMAIL', 'test@narrativeml.com')
TEST_USER_ID = os.getenv('TEST_USER_ID', 'test-user-12345')
TEST_USER_NAME = 'Test User'

def get_db_client():
    """Create and return MongoDB client with retry logic."""
    import time

    max_retries = 5
    retry_delay = 2  # seconds

    for attempt in range(1, max_retries + 1):
        try:
            print(f"   Attempt {attempt}/{max_retries}: Connecting to MongoDB...")
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            client.admin.command('ping')
            print("   ✅ Connected to MongoDB successfully")
            return client
        except Exception as e:
            if attempt < max_retries:
                print(f"   ⚠️  Connection attempt {attempt} failed: {e}")
                print(f"   Retrying in {retry_delay * attempt} seconds...")
                time.sleep(retry_delay * attempt)  # Exponential backoff
            else:
                print(f"\n❌ Failed to connect to MongoDB after {max_retries} attempts")
                print(f"   URI: {MONGODB_URI}")
                print(f"   Error: {e}")
                print("\n💡 Make sure MongoDB is running:")
                print("   - Local: mongod --dbpath /path/to/data")
                print("   - Docker: docker run -d -p 27017:27017 mongo:latest")
                print("   - CI: Check MongoDB service is started")
                sys.exit(1)

def seed_nextauth_user(db):
    """
    Seed NextAuth user in MongoDB.

    NextAuth MongoDB adapter creates these collections:
    - users: User accounts
    - accounts: OAuth provider accounts (optional for credentials provider)
    - sessions: User sessions (using JWT, so this might be empty)
    - verification_tokens: Email verification tokens
    """
    print("\n📝 Seeding NextAuth test user...")

    users_collection = db['users']

    # Check if user already exists
    existing_user = users_collection.find_one({'email': TEST_USER_EMAIL})

    if existing_user:
        print(f"   ℹ️  User {TEST_USER_EMAIL} already exists (ID: {existing_user.get('_id')})")
        print("   ♻️  Updating user data...")

        # Update existing user
        users_collection.update_one(
            {'email': TEST_USER_EMAIL},
            {
                '$set': {
                    'name': TEST_USER_NAME,
                    'emailVerified': datetime.now(UTC),
                    'image': None,
                }
            }
        )
        user_id = existing_user['_id']
    else:
        # Create new user (NextAuth MongoDB adapter schema)
        user_doc = {
            'name': TEST_USER_NAME,
            'email': TEST_USER_EMAIL,
            'emailVerified': datetime.now(UTC),
            'image': None,
        }

        result = users_collection.insert_one(user_doc)
        user_id = result.inserted_id
        print(f"   ✅ Created user {TEST_USER_EMAIL} (ID: {user_id})")

    return user_id

def seed_sample_dataset(db, user_id):
    """
    Seed a sample dataset for testing data workflows.
    Uses the UserData/DatasetMetadata schema from the backend.
    """
    print("\n📊 Seeding sample test dataset...")

    user_data_collection = db['user_data']

    # Check if test dataset already exists
    existing_dataset = user_data_collection.find_one({
        'user_id': str(user_id),
        'filename': 'e2e_test_sample.csv'
    })

    if existing_dataset:
        print(f"   ℹ️  Test dataset already exists (ID: {existing_dataset.get('_id')})")
        return existing_dataset['_id']

    # Create sample dataset metadata
    dataset_doc = {
        'user_id': str(user_id),
        'filename': 'e2e_test_sample.csv',
        'file_size': 1024,
        'row_count': 100,
        'column_count': 5,
        'uploaded_at': datetime.now(UTC),
        'is_processed': True,
        'processed_at': datetime.now(UTC),
        'schema': {
            'columns': ['id', 'name', 'age', 'city', 'score'],
            'types': {
                'id': 'int64',
                'name': 'object',
                'age': 'int64',
                'city': 'object',
                'score': 'float64'
            }
        },
        'statistics': {
            'numeric_columns': ['id', 'age', 'score'],
            'categorical_columns': ['name', 'city'],
            'missing_values': {'id': 0, 'name': 0, 'age': 2, 'city': 1, 'score': 3}
        },
        'quality_report': {
            'overall_quality_score': 0.95,
            'completeness': 0.97,
            'validity': 0.98,
            'consistency': 0.94,
            'issues': []
        }
    }

    result = user_data_collection.insert_one(dataset_doc)
    print(f"   ✅ Created sample dataset (ID: {result.inserted_id})")
    return result.inserted_id

def clear_test_data(db):
    """Clear existing test data to ensure clean slate."""
    print("\n🧹 Clearing existing test data...")

    # Clear test user
    result = db['users'].delete_many({'email': TEST_USER_EMAIL})
    if result.deleted_count > 0:
        print(f"   ✅ Removed {result.deleted_count} test user(s)")

    # Clear test user's data
    # Note: We don't know the user_id yet, so we'll rely on email matching
    # or create a marker field for test data

    print("   ✅ Test data cleared")

def verify_seed(db):
    """Verify that seeded data exists and is correct."""
    print("\n🔍 Verifying seeded data...")

    # Verify user
    user = db['users'].find_one({'email': TEST_USER_EMAIL})
    if user:
        print(f"   ✅ User verified: {user['email']} (ID: {user['_id']})")
    else:
        print("   ❌ User not found!")
        return False

    # Verify dataset
    dataset = db['user_data'].find_one({'user_id': str(user['_id'])})
    if dataset:
        print(f"   ✅ Dataset verified: {dataset['filename']}")
    else:
        print("   ℹ️  No datasets found (this is OK if not needed)")

    return True

def ensure_s3_bucket():
    """Create the test S3 bucket on the configured S3-compatible endpoint.

    Upload workflows hard-require working storage: without it the backend's
    /upload/secure call fails (or hangs in boto3 retries against real AWS) and
    every upload-dependent E2E spec dies in beforeEach (issue #191). Only runs
    when AWS_ENDPOINT_URL points at LocalStack/MinIO — never against real AWS.
    """
    endpoint_url = os.getenv('AWS_ENDPOINT_URL')
    if not endpoint_url:
        print("\n⚠️  AWS_ENDPOINT_URL is not set — no S3-compatible storage configured.")
        print("   Upload-dependent E2E specs WILL fail. Start LocalStack first:")
        print("   docker compose -f ../backend/docker-compose.test.yml up -d localstack")
        return

    bucket = os.getenv('AWS_BUCKET_NAME', 'test-bucket')
    try:
        import boto3
        client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', 'test'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', 'test'),
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
        )
        existing = {b['Name'] for b in client.list_buckets().get('Buckets', [])}
        if bucket not in existing:
            client.create_bucket(Bucket=bucket)
            print(f"\n✅ Created S3 bucket '{bucket}' at {endpoint_url}")
        else:
            print(f"\n✅ S3 bucket '{bucket}' already exists at {endpoint_url}")
    except Exception as e:
        print(f"\n❌ Could not ensure S3 bucket '{bucket}' at {endpoint_url}: {e}")
        print("   Upload-dependent E2E specs will fail without working storage.")
        sys.exit(1)


def main():
    """Main seeding logic."""
    print("=" * 60)
    print("E2E Test Data Seeding Script")
    print("=" * 60)
    print(f"\nMongoDB URI: {MONGODB_URI}")
    print(f"Test User Email: {TEST_USER_EMAIL}")
    print(f"Test User ID: {TEST_USER_ID}")

    # Connect to MongoDB
    client = get_db_client()
    db = client[MONGODB_DB]

    print(f"\n✅ Connected to database: {db.name}")

    try:
        # Optional: Clear existing test data for fresh start
        if '--clear' in sys.argv:
            clear_test_data(db)

        ensure_s3_bucket()

        # Seed test user
        user_id = seed_nextauth_user(db)

        # Seed sample dataset
        if '--with-data' in sys.argv:
            seed_sample_dataset(db, user_id)

        # Verify seeded data
        if verify_seed(db):
            print("\n" + "=" * 60)
            print("✅ E2E test data seeding completed successfully!")
            print("=" * 60)
            print("\nYou can now run E2E tests:")
            print("  cd apps/frontend")
            print("  npm run test:e2e:smoke")
        else:
            print("\n❌ Verification failed!")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()

if __name__ == '__main__':
    main()
