// ═══════════════════════════════════════════════════════════════
// MongoDB Initialization Script for Staging
// ═══════════════════════════════════════════════════════════════
//
// This script runs automatically when MongoDB container starts
// Creates application database and user with appropriate permissions
//
// ═══════════════════════════════════════════════════════════════

// Connect to admin database (required for user creation)
db = db.getSiblingDB('admin');

// Get password from environment variable
const appPassword = process.env.MONGODB_PASSWORD || 'changeme';

print('Creating narrative_staging database and application user...');

// Switch to application database
db = db.getSiblingDB('narrative_staging');

// Create application user with read/write permissions
db.createUser({
  user: 'narrative_user',
  pwd: appPassword,
  roles: [
    {
      role: 'readWrite',
      db: 'narrative_staging'
    },
    {
      role: 'dbAdmin',
      db: 'narrative_staging'
    }
  ]
});

print('✅ User narrative_user created successfully');

// Create initial collections (optional - Beanie will create them)
db.createCollection('datasets');
db.createCollection('transformations');
db.createCollection('models');
db.createCollection('users');

print('✅ Initial collections created');

// Create indexes for performance
db.datasets.createIndex({ user_id: 1 });
db.datasets.createIndex({ created_at: -1 });
db.datasets.createIndex({ status: 1 });

db.transformations.createIndex({ dataset_id: 1 });
db.transformations.createIndex({ created_at: -1 });

db.models.createIndex({ dataset_id: 1 });
db.models.createIndex({ user_id: 1 });
db.models.createIndex({ created_at: -1 });

db.users.createIndex({ email: 1 }, { unique: true });

print('✅ Indexes created successfully');
print('✅ MongoDB initialization complete');
