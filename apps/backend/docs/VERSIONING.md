# Dataset Versioning System

## Overview

The versioning system provides comprehensive version control for datasets, enabling history tracking, lineage management, and efficient storage through content deduplication.

## Architecture

### Components

1. **DatasetVersion Model** (`app/models/version.py`)
   - Stores version metadata and S3 file references
   - Tracks version lineage through `parent_version_id`
   - Manages version lifecycle (active, archived, deleted)

2. **VersioningService** (`app/services/versioning_service.py`)
   - Creates and manages dataset versions
   - Handles S3 storage and retrieval
   - Implements content deduplication
   - Manages version lifecycle operations

3. **S3 Storage Backend**
   - Stores version snapshots in S3
   - Path structure: `datasets/{user_id}/{dataset_id}/versions/{version_id}.parquet`
   - Supports content-based deduplication

## Version Lifecycle

### States

- **Active**: Current version, available for use
- **Archived**: Older version, preserved but not current
- **Deleted**: Soft-deleted, eligible for cleanup

### Transitions

```
Created → Active
Active → Archived (when new version created)
Active/Archived → Deleted (user deletion)
Deleted → Permanently Removed (cleanup job)
```

## Version Creation

### Automatic Versioning

Versions are automatically created when:
- Dataset is uploaded for the first time (initial version)
- Transformation is applied to a dataset
- Recipe is applied to a dataset
- Manual snapshot is requested

### Version Metadata

Each version includes:
```python
{
  "version_id": "v_abc123",
  "dataset_id": "ds_xyz789",
  "user_id": "user_456",
  "version_number": 3,
  "parent_version_id": "v_def456",  # Lineage tracking
  "file_path": "s3://bucket/datasets/user_456/ds_xyz789/versions/v_abc123.parquet",
  "content_hash": "sha256:...",
  "file_size_bytes": 1048576,
  "row_count": 10000,
  "column_count": 25,
  "description": "Applied normalization transformation",
  "transformation_config_id": "tc_123",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "last_accessed_at": "2024-01-15T10:30:00Z",
  "access_count": 5
}
```

## Lineage Tracking

### Parent-Child Relationships

Versions maintain lineage through `parent_version_id`:

```
v1 (initial upload)
  └─ v2 (normalize)
       └─ v3 (remove_outliers)
            └─ v4 (encode_categorical)
```

### Branching

When undoing and applying new transformations, history branches:

```
v1 → v2 → v3
       └─ v4 (after undo to v2, apply different transformation)
```

## Content Deduplication

### Hash-Based Deduplication

The system avoids storing duplicate content:

1. Calculate content hash (SHA-256) of dataset
2. Check if hash already exists in S3
3. If exists, reference existing file instead of uploading
4. If new, upload and store hash mapping

**Benefits**:
- Reduced storage costs
- Faster version creation
- Efficient for operations that don't modify data

### Example

```python
# User applies a filter that results in same data
# (e.g., filter removes 0 rows due to condition)
version1_hash = "sha256:abc123..."
version2_hash = "sha256:abc123..."  # Same!

# version2 references version1's S3 file
# No duplicate upload required
```

## Version Retrieval

### Get Version Metadata

```python
from app.services.versioning_service import versioning_service

version = await versioning_service.get_version(
    version_id="v_abc123",
    mark_accessed=True  # Updates last_accessed_at
)
```

### Get Version Content

```python
# Returns actual dataset bytes
content = await versioning_service.get_version_content(
    version_id="v_abc123"
)

# Load into DataFrame
import pandas as pd
import io
df = pd.read_parquet(io.BytesIO(content))
```

### List Versions

```python
# Get all versions for a dataset
versions = await versioning_service.list_versions(
    dataset_id="ds_xyz789",
    include_deleted=False
)
```

## Version Cleanup

### Automatic Cleanup

Background jobs periodically clean up:
- Deleted versions older than 30 days
- Versions with zero access count after 90 days (configurable)
- Orphaned S3 files with no version metadata

### Manual Cleanup

```python
# Permanently delete a version
await versioning_service.delete_version(
    version_id="v_abc123",
    permanent=True
)

# Archive old versions
await versioning_service.archive_old_versions(
    dataset_id="ds_xyz789",
    keep_latest=5  # Keep only 5 most recent versions
)
```

## Storage Optimization

### Parquet Format

All versions stored as Parquet for:
- Efficient compression (often 10x smaller than CSV)
- Fast columnar reads
- Schema preservation
- Metadata storage

### S3 Lifecycle Policies

Recommended S3 lifecycle configuration:
```json
{
  "Rules": [
    {
      "Id": "ArchiveOldVersions",
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

## Integration with Transformation History

The versioning system integrates with transformation history:

1. **Transformation Applied**: Creates new version
2. **Version Saved**: Stored in S3 with lineage
3. **History Updated**: Transformation step references version_id
4. **Undo Operation**: Restores dataset to previous version

See [Transformation History Documentation](../../claudedocs/TRANSFORMATION_HISTORY.md) for details.

## API Endpoints

### Version Management

```
GET    /api/v1/datasets/{id}/versions           - List versions
GET    /api/v1/datasets/{id}/versions/{vid}     - Get version details
POST   /api/v1/datasets/{id}/versions           - Create manual snapshot
DELETE /api/v1/datasets/{id}/versions/{vid}     - Delete version
GET    /api/v1/datasets/{id}/versions/{vid}/download - Download version
```

### Version Comparison

```
GET    /api/v1/datasets/{id}/versions/compare?v1={vid1}&v2={vid2}
```

Returns diff statistics between two versions.

## Performance Considerations

### Caching

- Version metadata cached in memory (TTL: 5 minutes)
- S3 content cached for frequently accessed versions
- LRU eviction policy for cache management

### Batch Operations

For multiple version operations, use batch endpoints:
```python
await versioning_service.batch_create_versions([
    {"dataset_id": "ds1", "content": data1},
    {"dataset_id": "ds2", "content": data2},
])
```

### Async S3 Operations

All S3 operations are async to prevent blocking:
```python
# Non-blocking S3 upload
await versioning_service.upload_version_async(version_id, content)
```

## Monitoring and Metrics

### Key Metrics

- Version creation rate
- Storage usage by dataset
- Deduplication efficiency (% of deduplicated versions)
- Average version size
- S3 upload/download latency

### Logging

All version operations are logged:
```python
logger.info(f"Created version {version_id} for dataset {dataset_id}")
logger.info(f"Version size: {file_size_bytes} bytes, hash: {content_hash}")
```

## Error Handling

### Common Errors

- `VersionNotFoundError`: Version ID doesn't exist
- `S3UploadError`: Failed to upload to S3
- `InvalidVersionStateError`: Operation not allowed in current state
- `StorageQuotaExceededError`: User storage limit exceeded

### Retry Logic

Failed S3 operations retry with exponential backoff:
- Initial delay: 1 second
- Max retries: 3
- Exponential factor: 2

## Security

### Access Control

- Users can only access versions of their own datasets
- Admin users can access all versions (audit purposes)
- Version deletion requires owner permissions

### Encryption

- S3 server-side encryption (SSE-S3) enabled
- Optional client-side encryption for sensitive data
- Encrypted version metadata in MongoDB

## Related Documentation

- [Transformation History](../../claudedocs/TRANSFORMATION_HISTORY.md) - Undo/redo with versioning
- [API Documentation](API.md) - Version API endpoints
- [Transformation Service](TRANSFORMATIONS.md) - Version creation during transformations
- [Test Standards](TEST_STANDARDS.md) - Testing version operations

## Configuration

### Environment Variables

```bash
# S3 Configuration
AWS_S3_BUCKET=narrative-modeling-datasets
AWS_REGION=us-east-1

# Versioning Settings
VERSION_RETENTION_DAYS=90
MAX_VERSIONS_PER_DATASET=100
ENABLE_VERSION_DEDUPLICATION=true

# Storage Limits
MAX_VERSION_SIZE_MB=500
USER_STORAGE_QUOTA_GB=50
```

### Feature Flags

```python
ENABLE_AUTO_VERSIONING = True
ENABLE_VERSION_CLEANUP = True
ENABLE_CONTENT_DEDUPLICATION = True
```
