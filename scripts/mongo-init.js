// MongoDB initialization script for production
// This script runs when the MongoDB container starts for the first time

// Create application database
db = db.getSiblingDB('narrative_modeling');

// Create application user with appropriate permissions
db.createUser({
  user: 'app_user',
  pwd: 'app_password', // This should be set via environment variable
  roles: [
    {
      role: 'readWrite',
      db: 'narrative_modeling'
    }
  ]
});

// Create indexes for better performance
db.user_data.createIndex({ "user_id": 1 });
db.user_data.createIndex({ "created_at": -1 });
db.user_data.createIndex({ "file_name": "text", "original_name": "text" });

db.ml_models.createIndex({ "user_id": 1 });
db.ml_models.createIndex({ "model_id": 1 }, { unique: true });
db.ml_models.createIndex({ "created_at": -1 });
db.ml_models.createIndex({ "is_active": 1 });

db.api_keys.createIndex({ "user_id": 1 });
db.api_keys.createIndex({ "key_id": 1 }, { unique: true });
db.api_keys.createIndex({ "key_hash": 1 }, { unique: true });
db.api_keys.createIndex({ "is_active": 1 });
db.api_keys.createIndex({ "expires_at": 1 });

db.ab_tests.createIndex({ "user_id": 1 });
db.ab_tests.createIndex({ "experiment_id": 1 }, { unique: true });
db.ab_tests.createIndex({ "status": 1 });
db.ab_tests.createIndex({ "created_at": -1 });

db.batch_jobs.createIndex({ "user_id": 1 });
db.batch_jobs.createIndex({ "job_id": 1 }, { unique: true });
db.batch_jobs.createIndex({ "status": 1 });
db.batch_jobs.createIndex({ "job_type": 1 });
db.batch_jobs.createIndex({ "created_at": -1 });
db.batch_jobs.createIndex({ "priority": -1 });

// Create TTL indexes for cleanup
db.batch_jobs.createIndex({ "completed_at": 1 }, { expireAfterSeconds: 30 * 24 * 60 * 60 }); // 30 days
db.analytics_results.createIndex({ "created_at": 1 }, { expireAfterSeconds: 90 * 24 * 60 * 60 }); // 90 days

print('MongoDB initialization completed successfully');
print('Created database: narrative_modeling');
print('Created user: app_user');
print('Created indexes for optimal performance');