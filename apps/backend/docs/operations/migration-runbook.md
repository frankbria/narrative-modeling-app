# UserData Model Migration Runbook

**Version**: 1.0.0
**Last Updated**: 2025-10-13
**Owner**: Development Team
**Status**: ✅ Ready for Use (Migration currently deferred - see Architecture Decision)

---

## Executive Summary

This runbook provides comprehensive procedures for migrating from the monolithic `UserData` model to the new three-collection architecture (`DatasetMetadata`, `TransformationConfig`, `ModelConfig`). While the migration is currently **deferred** due to architectural improvements that eliminated the immediate need, this runbook remains essential for:

1. **Future migrations** when data consolidation becomes necessary
2. **Emergency rollback** procedures if issues arise
3. **Best practices** documentation for similar migrations
4. **Team knowledge** preservation and onboarding

### Architecture Decision

The new model implementation uses **separate Beanie Document collections** rather than replacing the existing `UserData` collection. This approach:
- ✅ Eliminates immediate migration risk
- ✅ Maintains backward compatibility
- ✅ Allows gradual transition
- ✅ Preserves legacy data intact

**When Migration Will Be Required**:
- When storage optimization becomes priority (reducing data duplication)
- When legacy UserData collection is deprecated
- When unified data model is required for compliance/audit
- When performance optimization requires consolidated collections

---

## Table of Contents

1. [Pre-Migration Checklist](#pre-migration-checklist)
2. [Migration Overview](#migration-overview)
3. [Environment Preparation](#environment-preparation)
4. [Migration Execution](#migration-execution)
5. [Validation Procedures](#validation-procedures)
6. [Rollback Procedures](#rollback-procedures)
7. [Post-Migration Tasks](#post-migration-tasks)
8. [Troubleshooting](#troubleshooting)
9. [Performance Monitoring](#performance-monitoring)
10. [Communication Plan](#communication-plan)

---

## Pre-Migration Checklist

### 1. System Requirements

- [ ] MongoDB 5.0+ installed and running
- [ ] Python 3.11+ with uv environment
- [ ] Sufficient disk space (3x current UserData collection size)
- [ ] Backup storage configured (S3 or equivalent)
- [ ] Monitoring tools configured (Prometheus/Grafana)

### 2. Team Preparation

- [ ] All stakeholders notified (72 hours advance notice)
- [ ] Migration window scheduled during low-traffic period
- [ ] On-call engineers identified and briefed
- [ ] Rollback team designated (minimum 2 engineers)
- [ ] Communication channels established (Slack, email, status page)

### 3. Data Assessment

- [ ] UserData collection size measured
- [ ] Document count verified
- [ ] Average document size calculated
- [ ] Transformation history distribution analyzed
- [ ] PII data prevalence assessed

**Assessment Commands**:
```bash
# MongoDB assessment
mongosh narrative_modeling --eval "db.user_data.stats()"
mongosh narrative_modeling --eval "db.user_data.count()"

# Document size distribution
mongosh narrative_modeling --eval 'db.user_data.aggregate([
  {$project: {size: {$bsonSize: "$$ROOT"}}},
  {$group: {_id: null, avgSize: {$avg: "$size"}, maxSize: {$max: "$size"}}}
])'
```

### 4. Backup Verification

- [ ] Full MongoDB backup completed
- [ ] Backup restore tested successfully
- [ ] Backup stored in multiple locations
- [ ] Backup retention policy confirmed (90 days minimum)

**Backup Commands**:
```bash
# Full MongoDB backup
mongodump --uri="mongodb://localhost:27017/narrative_modeling" \
  --out="/backup/narrative_modeling_$(date +%Y%m%d_%H%M%S)"

# Verify backup integrity
mongorestore --dryRun --uri="mongodb://localhost:27017/narrative_modeling_test" \
  --dir="/backup/narrative_modeling_TIMESTAMP"
```

### 5. Test Environment Validation

- [ ] Test environment matches production (MongoDB version, data volume)
- [ ] Migration tests run successfully in test environment
- [ ] Performance benchmarks established
- [ ] Rollback procedure tested and documented

---

## Migration Overview

### Data Flow

```
┌─────────────────┐
│   UserData      │
│  (Monolithic)   │
└────────┬────────┘
         │
         ├──────────────────────────────┐
         │                              │
         ▼                              ▼
┌────────────────────┐        ┌──────────────────────┐
│ DatasetMetadata    │        │ TransformationConfig │
│ - File info        │        │ - Transform steps    │
│ - Schema           │        │ - History            │
│ - Statistics       │        │ - Validation         │
│ - PII report       │        └──────────────────────┘
│ - Quality          │
└────────────────────┘        ┌──────────────────────┐
                              │ ModelConfig          │
                              │ - Algorithm          │
                              │ - Hyperparameters    │
                              │ - Training metrics   │
                              └──────────────────────┘
```

### Field Mapping

#### UserData → DatasetMetadata

| UserData Field | DatasetMetadata Field | Transformation |
|----------------|----------------------|----------------|
| `user_id` | `user_id` | Direct copy |
| `filename` | `filename` | Direct copy |
| `original_filename` | `original_filename` | Direct copy |
| `s3_url` | `s3_url` | Direct copy |
| `num_rows` | `num_rows` | Use `row_count` if available, else `num_rows` |
| `num_columns` | `num_columns` | Direct copy |
| `data_schema` | `data_schema` | Convert to new SchemaField format |
| `contains_pii` | `pii_report.contains_pii` | Wrap in PIIReport object |
| `pii_report` | `pii_report.detection_details` | Restructure to PIIReport |
| `pii_risk_level` | `pii_report.risk_level` | Move to PIIReport |
| `pii_masked` | `pii_report.masked` | Move to PIIReport |
| `is_processed` | `is_processed` | Direct copy |
| `processed_at` | `processed_at` | Direct copy |
| `schema` | `inferred_schema` | Direct copy |
| `statistics` | `statistics` | Direct copy |
| `quality_report` | `quality_report` | Direct copy |
| `data_preview` | `data_preview` | Direct copy |
| `aiSummary` | `ai_summary` | Direct copy |
| `file_type` | `file_type` | Default to "csv" if null |
| `onboarding_progress` | `onboarding_progress` | Direct copy |
| `created_at` | `created_at` | Direct copy |
| `updated_at` | `updated_at` | Direct copy |

#### UserData → TransformationConfig

| UserData Field | TransformationConfig Field | Transformation |
|----------------|---------------------------|----------------|
| `user_id` | `user_id` | Direct copy |
| `id` (or generated) | `dataset_id` | Use document ID or generate UUID |
| Generated | `config_id` | Generate from `{dataset_id}_config` |
| `transformation_history` | `transformation_steps` | Convert to TransformationStep objects |
| `file_path` | `current_file_path` | Direct copy |
| Calculated | `is_applied` | True if transformation_history not empty |
| `updated_at` | `applied_at` | If transformations applied |
| Calculated | `total_transformations` | Count of transformation_history items |
| `created_at` | `created_at` | Direct copy |
| `updated_at` | `updated_at` | Direct copy |

### Estimated Duration

| Document Count | Estimated Duration | Throughput |
|---------------|-------------------|------------|
| 1,000 | < 10 seconds | ~100 docs/sec |
| 10,000 | < 100 seconds | ~100 docs/sec |
| 100,000 | < 1,000 seconds | ~100 docs/sec |
| 1,000,000 | < 3 hours | ~100 docs/sec |

*Note: Times based on test environment. Production times may vary based on hardware, network, and load.*

---

## Environment Preparation

### 1. Set Maintenance Mode

```bash
# Enable maintenance mode (prevents new data modifications)
curl -X POST http://localhost:8000/api/v1/admin/maintenance \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"enabled": true, "message": "Database migration in progress"}'
```

### 2. Stop Background Workers

```bash
# Stop Celery workers (if using)
sudo systemctl stop celery-worker

# Or kill background task processes
pkill -f "celery worker"
```

### 3. Verify Database Connections

```bash
# Check active connections
mongosh narrative_modeling --eval "db.serverStatus().connections"

# Expected: Low connection count (<10) during maintenance window
```

### 4. Create Migration Collections

```bash
# Collections will be auto-created by Beanie, but verify indexes
mongosh narrative_modeling --eval '
  db.createCollection("dataset_metadata")
  db.createCollection("transformation_configs")
  db.createCollection("model_configs")
'
```

---

## Migration Execution

### Step 1: Dry Run

**Purpose**: Validate migration logic without modifying data

```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/backend

# Run dry-run migration script
PYTHONPATH=. uv run python scripts/migrate_user_data.py --dry-run --verbose

# Expected output:
# ✓ Would migrate 10,523 documents
# ✓ Estimated duration: 105 seconds
# ✓ Storage impact: +2.1 GB (estimated)
# ✓ No errors detected
```

### Step 2: Batch Migration

**Purpose**: Migrate data in controllable batches

```bash
# Migrate in batches of 1,000 documents
PYTHONPATH=. uv run python scripts/migrate_user_data.py \
  --batch-size 1000 \
  --progress \
  --log-file /var/log/migration_$(date +%Y%m%d_%H%M%S).log

# Expected output (every 1000 docs):
# [2025-10-13 10:15:23] Batch 1/11: Migrated 1,000 docs (took 9.8s)
# [2025-10-13 10:15:33] Batch 2/11: Migrated 1,000 docs (took 9.5s)
# ...
# [2025-10-13 10:17:15] ✓ Migration complete: 10,523 docs in 112s
```

### Step 3: Real-time Monitoring

**Terminal 1** (Migration execution):
```bash
PYTHONPATH=. uv run python scripts/migrate_user_data.py --batch-size 1000
```

**Terminal 2** (Progress monitoring):
```bash
watch -n 5 'mongosh narrative_modeling --quiet --eval "
  printjson({
    user_data: db.user_data.count(),
    dataset_metadata: db.dataset_metadata.count(),
    transformation_configs: db.transformation_configs.count()
  })
"'
```

**Terminal 3** (Performance monitoring):
```bash
watch -n 5 'mongosh narrative_modeling --quiet --eval "db.serverStatus().opcounters"'
```

### Step 4: Verify Progress

```bash
# Check migration status
mongosh narrative_modeling --eval '
  printjson({
    total_user_data: db.user_data.count(),
    migrated_datasets: db.dataset_metadata.count(),
    migrated_configs: db.transformation_configs.count(),
    migration_ratio: (db.dataset_metadata.count() / db.user_data.count() * 100).toFixed(2) + "%"
  })
'
```

---

## Validation Procedures

### 1. Document Count Validation

```bash
# Verify all documents migrated
PYTHONPATH=. uv run python scripts/validate_migration.py --check-counts

# Expected:
# ✓ UserData count: 10,523
# ✓ DatasetMetadata count: 10,523
# ✓ TransformationConfig count: 10,523
# ✓ Ratio: 100.00%
```

### 2. Data Integrity Validation

```bash
# Run comprehensive data integrity tests
cd /home/frankbria/projects/narrative-modeling-app/apps/backend
PYTHONPATH=. uv run pytest tests/test_migrations/test_user_data_split.py::TestDataIntegrity -v

# Expected: All tests pass
```

### 3. Field Mapping Validation

```bash
# Validate field mappings
PYTHONPATH=. uv run python scripts/validate_migration.py --check-fields --sample-size 1000

# Expected:
# ✓ Validated 1,000 random documents
# ✓ All fields correctly mapped
# ✓ No data loss detected
# ✓ Schema conversion accurate
```

### 4. Transformation History Validation

```bash
# Verify transformation history preserved
mongosh narrative_modeling --eval '
  db.user_data.aggregate([
    {$match: {transformation_history: {$ne: []}}},
    {$count: "with_transformations"}
  ])
'

mongosh narrative_modeling --eval '
  db.transformation_configs.aggregate([
    {$match: {total_transformations: {$gt: 0}}},
    {$count: "with_transformations"}
  ])
'

# Counts should match
```

### 5. Performance Validation

```bash
# Run performance benchmarks
PYTHONPATH=. uv run pytest tests/test_migrations/test_user_data_split.py::TestPerformanceImpact -v

# Expected:
# ✓ Query performance within 10% of baseline
# ✓ No degradation in read operations
# ✓ Write operations comparable
```

---

## Rollback Procedures

### When to Rollback

Rollback should be initiated if:
- ❌ Data integrity validation fails (>0.1% data loss)
- ❌ Migration performance exceeds 3x estimated duration
- ❌ Application errors spike >10% during migration
- ❌ Critical production issues detected
- ❌ Stakeholder decision to abort

### Rollback Steps

#### Option 1: Restore from Backup (Fastest, Safest)

```bash
# Stop application servers
sudo systemctl stop backend-api

# Drop new collections
mongosh narrative_modeling --eval '
  db.dataset_metadata.drop()
  db.transformation_configs.drop()
  db.model_configs.drop()
'

# Restore from backup
mongorestore --uri="mongodb://localhost:27017" \
  --nsInclude="narrative_modeling.user_data" \
  --dir="/backup/narrative_modeling_TIMESTAMP"

# Restart application
sudo systemctl start backend-api

# Verify restoration
mongosh narrative_modeling --eval "db.user_data.count()"
```

**Rollback Time**: 5-15 minutes

#### Option 2: In-Place Rollback (If no backup restore needed)

```bash
# Run rollback script
cd /home/frankbria/projects/narrative-modeling-app/apps/backend
PYTHONPATH=. uv run python scripts/rollback_migration.py \
  --verify \
  --log-file /var/log/rollback_$(date +%Y%m%d_%H%M%S).log

# Expected:
# ✓ Reconstructing UserData from DatasetMetadata and TransformationConfig
# ✓ Verifying data integrity
# ✓ Rollback complete: 10,523 documents restored
```

**Rollback Time**: 10-30 minutes (depends on document count)

### Post-Rollback Validation

```bash
# Verify UserData collection restored
PYTHONPATH=. uv run python scripts/validate_migration.py --check-rollback

# Run application health checks
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/db

# Verify user functionality
PYTHONPATH=. uv run pytest tests/test_api/ -k "user_data" -v
```

---

## Post-Migration Tasks

### 1. Disable Legacy Write Paths

```python
# In user_data.py service layer, add deprecation warnings
import warnings

def create_user_data(data: dict):
    warnings.warn(
        "UserData model is deprecated. Use DatasetMetadata instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # ... rest of implementation
```

### 2. Update Application Code

- [ ] Update service layers to use new models
- [ ] Update API endpoints to return new model formats
- [ ] Update frontend to consume new API responses
- [ ] Add backward compatibility shims where needed

### 3. Create Indexes

```bash
# Create performance indexes on new collections
mongosh narrative_modeling --eval '
  db.dataset_metadata.createIndex({"user_id": 1, "created_at": -1})
  db.dataset_metadata.createIndex({"dataset_id": 1}, {unique: true})
  db.transformation_configs.createIndex({"user_id": 1, "dataset_id": 1})
  db.transformation_configs.createIndex({"config_id": 1}, {unique: true})
'
```

### 4. Monitor Performance

**First 24 Hours**:
- Monitor query response times (target: <10% degradation)
- Track error rates (target: <1% increase)
- Monitor MongoDB resource usage (CPU, memory, disk I/O)
- Review application logs for migration-related issues

**First Week**:
- Compare week-over-week performance metrics
- Gather user feedback on application performance
- Analyze slow query logs
- Optimize indexes based on actual usage patterns

### 5. Cleanup (After 30 Days)

```bash
# Archive legacy UserData collection (after 30 days of stability)
mongodump --db narrative_modeling --collection user_data \
  --out /archive/user_data_archive_$(date +%Y%m%d)

# Optional: Drop legacy collection (with caution!)
# mongosh narrative_modeling --eval "db.user_data.drop()"
```

---

## Troubleshooting

### Issue: Migration Script Crashes

**Symptoms**: Python script exits with traceback

**Diagnosis**:
```bash
# Check logs
tail -f /var/log/migration_TIMESTAMP.log

# Check MongoDB errors
mongosh narrative_modeling --eval "db.adminCommand({getLog: 'global'})"
```

**Solutions**:
1. **Memory Error**: Reduce batch size (`--batch-size 500`)
2. **Connection Timeout**: Increase MongoDB timeout in script
3. **Validation Error**: Fix data quality issues in source documents

### Issue: Data Loss Detected

**Symptoms**: Validation shows missing documents or fields

**Diagnosis**:
```bash
# Find missing documents
PYTHONPATH=. uv run python scripts/find_missing_docs.py

# Compare field counts
mongosh narrative_modeling --eval '
  var ud = db.user_data.findOne()
  var dm = db.dataset_metadata.findOne()
  printjson({user_data_fields: Object.keys(ud), dataset_metadata_fields: Object.keys(dm)})
'
```

**Solutions**:
1. **Immediate**: Halt migration, initiate rollback
2. **Analysis**: Identify root cause (script bug, data corruption)
3. **Fix**: Correct migration script, re-run from last checkpoint

### Issue: Performance Degradation

**Symptoms**: Queries slower than baseline after migration

**Diagnosis**:
```bash
# Analyze slow queries
mongosh narrative_modeling --eval "db.setProfilingLevel(2)"

# Check query plans
mongosh narrative_modeling --eval '
  db.dataset_metadata.find({user_id: "test_user"}).explain("executionStats")
'
```

**Solutions**:
1. **Missing Indexes**: Create indexes on frequently queried fields
2. **Query Optimization**: Rewrite queries to use new model structure
3. **Connection Pooling**: Adjust MongoDB connection pool size

### Issue: Application Errors After Migration

**Symptoms**: 500 errors, failed API requests

**Diagnosis**:
```bash
# Check application logs
tail -f /var/log/backend-api.log | grep ERROR

# Test API endpoints
curl -X GET http://localhost:8000/api/v1/datasets \
  -H "Authorization: Bearer $TEST_TOKEN"
```

**Solutions**:
1. **Model Compatibility**: Update Pydantic models to handle both old and new formats
2. **Service Layer**: Add backward compatibility shims
3. **Data Format**: Ensure API responses match expected format

---

## Performance Monitoring

### Key Metrics to Track

| Metric | Baseline | Target | Alert Threshold |
|--------|----------|--------|-----------------|
| Query response time | 50ms | <55ms | >75ms |
| Document count ratio | 1:1 | 1:1 | <0.99 |
| Error rate | 0.1% | <0.2% | >1% |
| Migration throughput | N/A | 100 docs/sec | <50 docs/sec |
| Database CPU usage | 30% | <40% | >60% |
| Database memory usage | 2GB | <2.5GB | >3GB |

### Monitoring Commands

```bash
# Real-time performance monitoring
watch -n 5 'mongosh narrative_modeling --quiet --eval "
  db.serverStatus().opcounters
"'

# Application health check
while true; do
  curl -s http://localhost:8000/api/v1/health | jq .
  sleep 5
done

# Query performance test
time mongosh narrative_modeling --quiet --eval '
  db.dataset_metadata.find({user_id: "test_user"}).limit(100).toArray()
'
```

---

## Communication Plan

### Pre-Migration (T-72 hours)

**Stakeholders**: All users, development team, operations team

**Message**:
```
📢 Scheduled Maintenance - Database Migration

Date: [DATE]
Time: [START_TIME] - [END_TIME] (UTC)
Duration: ~2 hours
Impact: Read-only mode during migration

What's happening:
We're upgrading our database architecture for improved performance
and scalability. During the maintenance window, you can view
existing data but cannot upload new datasets or run new analyses.

Prepared by: Development Team
Questions: dev-team@company.com
```

### During Migration (T-0)

**Stakeholders**: Development team, operations team

**Status Updates** (every 30 minutes):
```
✅ Migration Status Update #1 (T+30min)
- Progress: 3,500/10,523 documents (33%)
- Performance: 110 docs/sec (on target)
- Issues: None
- ETA: 1 hour 15 minutes
```

### Post-Migration (T+Complete)

**Stakeholders**: All users

**Message**:
```
✅ Migration Complete

The database migration has been completed successfully.
All features are now available.

Results:
- Documents migrated: 10,523
- Duration: 1 hour 52 minutes
- Data integrity: 100%
- Performance: Within normal range

Thank you for your patience.
```

### Rollback Scenario

**Stakeholders**: All users, executive team

**Message**:
```
⚠️ Migration Rollback in Progress

We encountered [ISSUE] during the database migration and
are rolling back to the previous stable state.

Impact: Service will be unavailable for ~15 minutes
ETA: [TIME]
Status: Rollback in progress

Your data is safe and backed up. We will reschedule
the migration after addressing the issue.
```

---

## Testing Checklist

Before production migration, verify all tests pass:

```bash
cd /home/frankbria/projects/narrative-modeling-app/apps/backend

# Run all migration tests
PYTHONPATH=. uv run pytest tests/test_migrations/test_user_data_split.py -v

# Expected results:
# ✓ TestMigrationLogic::test_migrate_single_document PASSED
# ✓ TestMigrationLogic::test_migrate_document_without_transformations PASSED
# ✓ TestMigrationLogic::test_migrate_document_with_pii PASSED
# ✓ TestVolumeMigration::test_migrate_1k_documents PASSED
# ✓ TestVolumeMigration::test_migrate_10k_documents PASSED
# ✓ TestVolumeMigration::test_migrate_100k_documents PASSED (slow)
# ✓ TestDataIntegrity::test_no_data_loss PASSED
# ✓ TestDataIntegrity::test_field_mapping_accuracy PASSED
# ✓ TestDataIntegrity::test_schema_preservation PASSED
# ✓ TestRollbackProcedure::test_rollback_single_document PASSED
# ✓ TestRollbackProcedure::test_rollback_preserves_all_data PASSED
# ✓ TestPerformanceImpact::test_migration_performance_metrics PASSED
# ✓ TestEdgeCases::test_migrate_empty_transformation_history PASSED
# ✓ TestEdgeCases::test_migrate_missing_optional_fields PASSED
# ✓ TestEdgeCases::test_migrate_with_invalid_transformation_data PASSED
```

---

## Success Criteria

Migration is considered successful when:

- ✅ 100% of documents migrated (document count match)
- ✅ 0% data loss (all fields preserved and validated)
- ✅ Performance within 10% of baseline
- ✅ No application errors during or after migration
- ✅ All validation tests pass
- ✅ Rollback procedure tested and documented
- ✅ Stakeholders informed and satisfied

---

## Appendix A: Script Templates

### Migration Script Template

```python
# scripts/migrate_user_data.py
"""
UserData to DatasetMetadata/TransformationConfig migration script.
"""
import asyncio
import logging
from typing import List
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.user_data import UserData
from app.models.dataset import DatasetMetadata
from app.models.transformation import TransformationConfig


async def migrate_batch(user_data_docs: List[UserData]) -> dict:
    """Migrate a batch of UserData documents."""
    # Implementation from test_user_data_split.py
    pass


async def main():
    """Main migration entry point."""
    # Parse command line arguments
    # Connect to MongoDB
    # Run migration in batches
    # Validate results
    pass


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Appendix B: Contact Information

| Role | Name | Contact | Availability |
|------|------|---------|--------------|
| Migration Lead | [NAME] | [EMAIL] | 24/7 during migration |
| Database Admin | [NAME] | [EMAIL] | 24/7 during migration |
| On-Call Engineer | [NAME] | [PHONE] | 24/7 during migration |
| Product Manager | [NAME] | [EMAIL] | Business hours |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-10-13 | Development Team | Initial runbook creation |

---

**End of Runbook**
