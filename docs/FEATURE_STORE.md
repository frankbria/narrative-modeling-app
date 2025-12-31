# Feature Store API Documentation

## Overview

The Feature Store provides a centralized repository for managing, versioning, and reusing feature engineering transformations across multiple datasets and models. It enables:

- **Feature Reusability**: Define features once, use across multiple datasets
- **Version Control**: Track feature evolution with automatic versioning
- **Collaboration**: Share features across teams with public/private access controls
- **Consistency**: Ensure consistent feature computation across train/serve environments

## Architecture

### Components

1. **Feature Definitions** (`FeatureDefinition`): Metadata about a feature
   - Name, description, category, tags
   - Input/output specifications
   - Ownership and access control

2. **Stored Features** (`StoredFeature`): Executable feature implementations
   - Definition code (pandas/numpy operations)
   - Validation and execution engine
   - Performance metrics

3. **Feature Versions** (`FeatureVersion`): Historical snapshots
   - Immutable feature code snapshots
   - Change tracking and lineage
   - Rollback capability

4. **Feature Collections**: Logical groupings
   - Related features bundled together
   - Dataset-specific feature sets
   - Model-specific feature pipelines

### Data Model

```python
FeatureDefinition
├── feature_id: str
├── name: str
├── description: str
├── category: str (transformation | aggregation | encoding | custom)
├── tags: List[str]
├── definition_type: str
├── definition_code: str
├── input_requirements: Dict[str, str]
├── output_type: str
├── output_column_name: str
├── is_public: bool
├── user_id: str
├── created_at: datetime
└── updated_at: datetime

StoredFeature
├── feature_id: str
├── current_version: int
├── definition: FeatureDefinition
├── validation_status: str (pending | validated | failed)
└── performance_metrics: Dict

FeatureVersion
├── version_id: str
├── feature_id: str
├── version_number: int
├── definition_code: str
├── changes_description: str
├── created_at: datetime
└── created_by: str

FeatureCollection
├── collection_id: str
├── name: str
├── description: str
├── feature_ids: List[str]
├── user_id: str
└── created_at: datetime
```

## API Endpoints

### Create Feature

**POST** `/api/v1/feature-store/features/`

Creates a new feature definition and stores it in the feature store.

**Request Body:**
```json
{
  "name": "customer_lifetime_value",
  "description": "Calculate total customer spend over lifetime",
  "category": "aggregation",
  "tags": ["customer", "revenue", "business"],
  "definition_type": "aggregation",
  "definition_code": "df['customer_ltv'] = df.groupby('customer_id')['purchase_amount'].transform('sum')",
  "input_requirements": {
    "customer_id": "string",
    "purchase_amount": "float"
  },
  "output_type": "float",
  "output_column_name": "customer_ltv",
  "is_public": false
}
```

**Response (201 Created):**
```json
{
  "feature_id": "feat_abc123",
  "name": "customer_lifetime_value",
  "version": 1,
  "created_at": "2025-12-31T12:00:00Z"
}
```

### List Features

**GET** `/api/v1/feature-store/features/`

Retrieve all features accessible to the current user.

**Query Parameters:**
- `category` (optional): Filter by category
- `tag` (optional): Filter by tag
- `is_public` (optional): Filter by visibility

**Response (200 OK):**
```json
{
  "features": [
    {
      "feature_id": "feat_abc123",
      "name": "customer_lifetime_value",
      "category": "aggregation",
      "tags": ["customer", "revenue"],
      "is_public": false,
      "version": 2
    }
  ],
  "total": 1
}
```

### Get Feature

**GET** `/api/v1/feature-store/features/{feature_id}`

Retrieve a specific feature by ID.

**Response (200 OK):**
```json
{
  "feature_id": "feat_abc123",
  "name": "customer_lifetime_value",
  "description": "Calculate total customer spend over lifetime",
  "category": "aggregation",
  "tags": ["customer", "revenue", "business"],
  "definition_code": "df['customer_ltv'] = df.groupby('customer_id')['purchase_amount'].transform('sum')",
  "input_requirements": {
    "customer_id": "string",
    "purchase_amount": "float"
  },
  "output_type": "float",
  "output_column_name": "customer_ltv",
  "current_version": 2,
  "created_at": "2025-12-31T12:00:00Z",
  "updated_at": "2025-12-31T13:30:00Z"
}
```

### Update Feature

**PUT** `/api/v1/feature-store/features/{feature_id}`

Update an existing feature. Creates a new version automatically.

**Request Body:**
```json
{
  "definition_code": "df['customer_ltv'] = df.groupby('customer_id')['purchase_amount'].transform('mean')",
  "changes_description": "Changed from sum to mean for better outlier handling"
}
```

**Response (200 OK):**
```json
{
  "feature_id": "feat_abc123",
  "version": 3,
  "message": "Feature updated successfully"
}
```

### Delete Feature

**DELETE** `/api/v1/feature-store/features/{feature_id}`

Delete a feature and all its versions.

**Response (204 No Content)**

### Apply Feature

**POST** `/api/v1/feature-store/features/{feature_id}/apply`

Apply a feature transformation to a dataset.

**Request Body:**
```json
{
  "dataset_id": "ds_xyz789",
  "version": 2
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "output_column": "customer_ltv",
  "rows_processed": 10000,
  "execution_time_ms": 250
}
```

### Feature Versions

**GET** `/api/v1/feature-store/features/{feature_id}/versions`

List all versions of a feature.

**Response (200 OK):**
```json
{
  "versions": [
    {
      "version": 2,
      "created_at": "2025-12-31T13:30:00Z",
      "changes": "Changed from sum to mean for better outlier handling"
    },
    {
      "version": 1,
      "created_at": "2025-12-31T12:00:00Z",
      "changes": "Initial version"
    }
  ]
}
```

### Feature Collections

**POST** `/api/v1/feature-store/collections`

Create a feature collection.

**Request Body:**
```json
{
  "name": "customer_analytics_features",
  "description": "Standard features for customer analytics",
  "feature_ids": ["feat_abc123", "feat_def456", "feat_ghi789"]
}
```

**Response (201 Created):**
```json
{
  "collection_id": "coll_123abc",
  "name": "customer_analytics_features",
  "feature_count": 3
}
```

## Security

### Feature Code Validation

All feature code is validated before execution to prevent:
- File system access
- Module imports
- System command execution
- Arbitrary code execution via `eval()`/`exec()`

**Allowed operations:**
- Pandas DataFrame operations
- NumPy array operations
- Basic Python arithmetic and logic

**Example allowed code:**
```python
# ✅ Allowed
df['new_col'] = df['col1'] + df['col2']
df['mean_val'] = df.groupby('group')['value'].transform('mean')
df['normalized'] = (df['value'] - df['value'].mean()) / df['value'].std()
```

**Example forbidden code:**
```python
# ❌ Forbidden
import os  # Module imports blocked
open('file.txt')  # File access blocked
eval(user_input)  # Code execution blocked
```

### Access Control

- **Private features**: Only accessible to the creating user
- **Public features**: Accessible to all users in the organization
- Features can be made public/private via the `is_public` flag

## Best Practices

### 1. Naming Conventions

- Use descriptive, snake_case names
- Include the transformation type: `customer_total_purchases`, `product_price_ratio`
- Avoid abbreviations unless domain-standard

### 2. Documentation

- Always provide clear descriptions
- Document input requirements and expected data types
- Explain the business logic and use case

### 3. Versioning

- Create new versions for bug fixes or logic changes
- Document changes in `changes_description`
- Never delete old versions that are in use

### 4. Testing

Test features before deployment:
```python
# Test on sample data
sample_df = pd.DataFrame({
    'customer_id': ['A', 'A', 'B'],
    'purchase_amount': [100, 150, 200]
})

# Apply feature
result = await feature_store.apply_feature(sample_df, feature_id)
assert 'customer_ltv' in result.columns
```

### 5. Performance

- Avoid cartesian products or nested loops
- Use vectorized pandas operations
- Test on representative data volumes

## Error Handling

### Common Errors

**ValidationError (400):**
- Missing required input columns
- Invalid code (contains forbidden operations)
- Type mismatches

**NotFoundError (404):**
- Feature ID doesn't exist
- Version doesn't exist

**PermissionDeniedError (403):**
- Attempting to modify someone else's private feature
- Insufficient permissions

### Example Error Response

```json
{
  "error": "ValidationError",
  "message": "Feature code contains forbidden operation: import",
  "details": {
    "code_line": "import os",
    "forbidden_pattern": "import "
  }
}
```

## Examples

### Creating a Simple Transformation

```python
# Create a feature that calculates age from birthdate
feature = {
    "name": "customer_age",
    "description": "Calculate customer age from birthdate",
    "category": "transformation",
    "definition_code": "df['age'] = (pd.Timestamp.now() - pd.to_datetime(df['birthdate'])).dt.days // 365",
    "input_requirements": {"birthdate": "datetime"},
    "output_type": "int",
    "output_column_name": "age"
}
```

### Creating an Aggregation

```python
# Create a feature that calculates average order value per customer
feature = {
    "name": "avg_order_value",
    "description": "Average order value per customer",
    "category": "aggregation",
    "definition_code": "df['avg_order_value'] = df.groupby('customer_id')['order_total'].transform('mean')",
    "input_requirements": {
        "customer_id": "string",
        "order_total": "float"
    },
    "output_type": "float",
    "output_column_name": "avg_order_value"
}
```

### Creating an Encoding

```python
# Create a feature that encodes categorical variables
feature = {
    "name": "category_encoded",
    "description": "One-hot encode product category",
    "category": "encoding",
    "definition_code": "df = pd.get_dummies(df, columns=['product_category'], prefix='cat')",
    "input_requirements": {"product_category": "string"},
    "output_type": "int",
    "output_column_name": "cat_*"
}
```

## Integration with Model Training

Features can be applied during model training pipeline:

```python
# 1. Load dataset
dataset = await dataset_service.get_dataset(dataset_id)

# 2. Apply features from collection
collection = await feature_store.get_collection(collection_id)
for feature_id in collection.feature_ids:
    dataset = await feature_store.apply_feature(dataset, feature_id)

# 3. Train model with engineered features
model = await model_training.train(dataset, target_column)
```

## Roadmap

Planned enhancements:
- **Feature dependencies**: Declare feature prerequisites
- **Automatic testing**: Validate features on sample data
- **Performance profiling**: Track execution time and resource usage
- **Feature lineage**: Visualize feature dependencies and usage
- **Scheduled updates**: Periodically re-apply features to datasets
- **Feature monitoring**: Alert on drift or data quality issues
