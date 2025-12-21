# Transformation Service

## Overview

The Transformation Service provides a comprehensive data transformation pipeline for cleaning, preprocessing, and preparing datasets for machine learning. It supports 30+ transformation types with preview, validation, and versioning capabilities.

## Architecture

### Core Components

1. **TransformationService** (`app/services/transformation_service.py`)
   - Orchestrates transformation operations
   - Manages transformation configurations
   - Integrates with versioning system

2. **TransformationEngine** (`app/services/transformation_engine/`)
   - Executes individual transformation operations
   - Validates transformation parameters
   - Tracks data quality metrics

3. **TransformationConfig Model** (`app/models/transformation.py`)
   - Stores transformation history and configuration
   - Tracks current position for undo/redo
   - Manages transformation lineage

4. **HistoryService** (`app/services/history_service.py`)
   - Provides undo/redo functionality
   - Manages transformation navigation
   - Maintains version consistency

## Transformation Types

### Data Cleaning

- **`remove_duplicates`** - Remove duplicate rows based on columns
- **`remove_nulls`** - Remove rows with null values
- **`trim_whitespace`** - Trim leading/trailing whitespace
- **`standardize_case`** - Standardize text case (upper/lower/title)
- **`remove_special_chars`** - Remove special characters from text

### Missing Value Handling

- **`fill_nulls_mean`** - Fill nulls with column mean
- **`fill_nulls_median`** - Fill nulls with column median
- **`fill_nulls_mode`** - Fill nulls with most frequent value
- **`fill_nulls_constant`** - Fill nulls with constant value
- **`fill_nulls_forward`** - Forward fill nulls
- **`fill_nulls_backward`** - Backward fill nulls
- **`drop_nulls`** - Drop rows with nulls

### Data Type Operations

- **`convert_type`** - Convert column data type
- **`parse_datetime`** - Parse strings to datetime
- **`extract_date_part`** - Extract year/month/day from datetime
- **`boolean_mapping`** - Map values to boolean

### Feature Engineering

- **`create_bins`** - Bin continuous values into categories
- **`one_hot_encode`** - One-hot encode categorical columns
- **`label_encode`** - Label encode categorical columns
- **`normalize`** - Normalize numeric columns (0-1 range)
- **`standardize`** - Standardize numeric columns (mean=0, std=1)
- **`log_transform`** - Apply logarithmic transformation
- **`polynomial_features`** - Create polynomial feature combinations

### Outlier Detection

- **`remove_outliers_iqr`** - Remove outliers using IQR method
- **`remove_outliers_zscore`** - Remove outliers using Z-score
- **`cap_outliers`** - Cap outliers at threshold values
- **`winsorize`** - Winsorize extreme values

### Column Operations

- **`rename_column`** - Rename a column
- **`drop_column`** - Remove a column
- **`reorder_columns`** - Change column order
- **`combine_columns`** - Combine multiple columns
- **`split_column`** - Split column into multiple columns

### Row Operations

- **`filter_rows`** - Filter rows by condition
- **`sample_rows`** - Random sample of rows
- **`sort_rows`** - Sort rows by columns

## Transformation Workflow

### 1. Preview Transformation

Preview transformation results before applying:

```python
from app.services.transformation_service import transformation_service

preview = await transformation_service.preview_transformation(
    dataset_id="ds_123",
    transformation_type="normalize",
    column="price",
    parameters={"method": "min_max"},
    preview_rows=100  # Preview first 100 rows
)

# Returns:
# {
#   "preview_data": [...],  # Sample rows after transformation
#   "affected_rows": 10000,
#   "affected_columns": ["price"],
#   "stats_before": {"price": {"min": 0, "max": 1000}},
#   "stats_after": {"price": {"min": 0.0, "max": 1.0}},
#   "warnings": []
# }
```

### 2. Validate Transformation

Validate parameters before applying:

```python
validation = await transformation_service.validate_transformation(
    dataset_id="ds_123",
    transformation_type="fill_nulls_mean",
    column="age",
    parameters={}
)

# Returns:
# {
#   "is_valid": true,
#   "errors": [],
#   "warnings": ["Column 'age' has 15% null values"],
#   "suggestions": ["Consider investigating why age is missing"]
# }
```

### 3. Apply Transformation

Apply transformation to dataset:

```python
result = await transformation_service.apply_transformation(
    dataset_id="ds_123",
    transformation_type="normalize",
    column="price",
    parameters={"method": "min_max"},
    user_id="user_456",
    save_as_new=False  # Update existing dataset
)

# Returns:
# {
#   "success": true,
#   "dataset_id": "ds_123",
#   "transformation_id": "t_789",
#   "affected_rows": 10000,
#   "affected_columns": ["price"],
#   "execution_time_ms": 1250,
#   "version_id": "v_new123"  # New version created
# }
```

### 4. Undo/Redo

Navigate transformation history:

```python
from app.services.history_service import history_service

# Undo last transformation
undo_result = await history_service.undo(
    dataset_id="ds_123",
    user_id="user_456"
)

# Redo transformation
redo_result = await history_service.redo(
    dataset_id="ds_123",
    user_id="user_456"
)

# Jump to specific position
jump_result = await history_service.jump_to_position(
    dataset_id="ds_123",
    position=5,
    user_id="user_456"
)
```

See [Transformation History Documentation](../../claudedocs/TRANSFORMATION_HISTORY.md) for details.

## Transformation Configuration

### TransformationConfig Model

Stores all transformations applied to a dataset:

```python
{
  "config_id": "tc_123",
  "dataset_id": "ds_456",
  "user_id": "user_789",
  "transformation_steps": [
    {
      "transformation_type": "remove_duplicates",
      "column": null,
      "columns": ["id", "name"],
      "parameters": {},
      "applied_at": "2024-01-15T10:00:00Z",
      "version_id": "v_001",
      "rows_affected": 150,
      "data_loss_percentage": 1.5
    },
    {
      "transformation_type": "fill_nulls_mean",
      "column": "age",
      "columns": null,
      "parameters": {},
      "applied_at": "2024-01-15T10:05:00Z",
      "version_id": "v_002",
      "rows_affected": 230,
      "data_loss_percentage": 0.0
    }
  ],
  "current_position": 1,  # For undo/redo navigation
  "is_applied": true,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:05:00Z"
}
```

### Current Position Tracking

The `current_position` field enables undo/redo:
- `-1`: Initial state (no transformations)
- `0`: First transformation applied
- `n`: n-th transformation applied

### History Branching

When undoing and applying new transformation, forward history is truncated:

```python
# Initial state
steps = [T1, T2, T3]
current_position = 2

# Undo twice
current_position = 0  # Now at T1

# Apply new transformation T4
steps = [T1, T4]  # T2 and T3 are removed
current_position = 1
```

## Transformation Parameters

### Common Parameters

Most transformations accept:
- `column`: Single column name
- `columns`: List of column names
- `parameters`: Transformation-specific parameters

### Parameter Validation

Parameters are validated using Pydantic schemas:

```python
# Example: Normalize transformation
class NormalizeParameters(BaseModel):
    method: Literal["min_max", "z_score", "robust"] = "min_max"
    feature_range: Tuple[float, float] = (0, 1)

# Invalid parameters raise ValidationError
await transformation_service.apply_transformation(
    transformation_type="normalize",
    column="price",
    parameters={"method": "invalid"}  # ❌ ValidationError
)
```

### Type-Specific Parameters

Each transformation type has specific parameters:

**Binning**:
```python
parameters = {
    "bins": 5,  # Number of bins
    "labels": ["Low", "Medium-Low", "Medium", "Medium-High", "High"],
    "strategy": "quantile"  # or "uniform", "kmeans"
}
```

**Outlier Removal**:
```python
parameters = {
    "method": "iqr",  # or "zscore"
    "threshold": 1.5,  # IQR multiplier or Z-score threshold
    "replace_with": "median"  # or "mean", "null", "remove"
}
```

**One-Hot Encoding**:
```python
parameters = {
    "drop_first": True,  # Drop first category to avoid multicollinearity
    "handle_unknown": "ignore"  # or "error"
}
```

## Quality Metrics

### Data Loss Tracking

Each transformation tracks data loss:

```python
{
  "rows_before": 10000,
  "rows_after": 9850,
  "rows_affected": 150,
  "data_loss_percentage": 1.5,  # (150/10000) * 100
  "columns_affected": ["age", "income"]
}
```

### Quality Warnings

Transformations may generate warnings:

- **High data loss**: >10% of rows removed
- **Type conversion issues**: Values couldn't be converted
- **Null introduction**: Transformation created new nulls
- **Outlier detection**: Many outliers detected
- **Performance**: Transformation took >10 seconds

## Recipes

### Transformation Recipes

Save transformation sequences as reusable recipes:

```python
from app.services.recipe_service import recipe_service

# Create recipe from current transformations
recipe = await recipe_service.create_recipe(
    name="Standard Preprocessing",
    description="Remove duplicates, handle nulls, normalize",
    transformation_config_id="tc_123",
    user_id="user_456"
)

# Apply recipe to different dataset
result = await recipe_service.apply_recipe(
    recipe_id=recipe.recipe_id,
    dataset_id="ds_new",
    user_id="user_456"
)
```

See [Recipe System Documentation](RECIPE_SYSTEM.md) for details.

## Performance Optimization

### Lazy Execution

Transformations are executed lazily when possible:

```python
# Multiple transformations batched into single operation
pipeline = TransformationPipeline()
pipeline.add(remove_duplicates())
pipeline.add(fill_nulls_mean())
pipeline.add(normalize())

# All executed in single pass over data
result = await pipeline.execute(df)
```

### Parallel Processing

Large datasets processed in parallel chunks:

```python
# Automatically parallelized for datasets >1M rows
result = await transformation_service.apply_transformation(
    dataset_id="large_dataset",  # 10M rows
    transformation_type="normalize",
    column="price",
    n_workers=4  # Use 4 parallel workers
)
```

### Caching

Transformation results cached for repeated operations:

```python
# First call: Computes and caches
preview1 = await transformation_service.preview_transformation(...)

# Second call with same parameters: Uses cache
preview2 = await transformation_service.preview_transformation(...)
# Instant response from cache
```

## Error Handling

### Common Errors

- `InvalidTransformationTypeError`: Unknown transformation type
- `ColumnNotFoundError`: Column doesn't exist in dataset
- `IncompatibleDataTypeError`: Column type incompatible with transformation
- `ParameterValidationError`: Invalid transformation parameters
- `TransformationExecutionError`: Error during transformation execution

### Error Recovery

Failed transformations don't modify the dataset:

```python
try:
    await transformation_service.apply_transformation(...)
except TransformationExecutionError as e:
    # Dataset remains unchanged
    # Previous version still active
    logger.error(f"Transformation failed: {e}")
```

## Testing

### Unit Tests

Test transformation logic in isolation:

```python
# tests/test_transformation_engine/test_normalize.py
def test_normalize_min_max():
    engine = TransformationEngine()
    df = pd.DataFrame({"price": [10, 20, 30]})

    result = engine.normalize(
        df,
        column="price",
        method="min_max",
        feature_range=(0, 1)
    )

    assert result["price"].min() == 0.0
    assert result["price"].max() == 1.0
```

### Integration Tests

Test full transformation workflow:

```python
# tests/integration/test_transformation_service.py
@pytest.mark.integration
async def test_apply_transformation_creates_version(
    transformation_service,
    sample_dataset
):
    result = await transformation_service.apply_transformation(
        dataset_id=sample_dataset.dataset_id,
        transformation_type="normalize",
        column="price",
        user_id="test_user"
    )

    assert result["success"] is True
    assert result["version_id"] is not None

    # Verify version created
    version = await versioning_service.get_version(
        result["version_id"]
    )
    assert version is not None
```

See [Test Standards](TEST_STANDARDS.md) for testing requirements.

## API Endpoints

### Transformation Operations

```
GET    /api/v1/transformations/types                    - List transformation types
POST   /api/v1/transformations/preview                  - Preview transformation
POST   /api/v1/transformations/apply                    - Apply transformation
POST   /api/v1/transformations/validate                 - Validate transformation
```

### Configuration Management

```
GET    /api/v1/transformations/datasets/{id}/config    - Get transformation config
DELETE /api/v1/transformations/datasets/{id}/config    - Clear transformation config
```

### History Management

```
GET    /api/v1/transformations/datasets/{id}/history       - Get transformation history
POST   /api/v1/transformations/datasets/{id}/history/undo  - Undo transformation
POST   /api/v1/transformations/datasets/{id}/history/redo  - Redo transformation
POST   /api/v1/transformations/datasets/{id}/history/jump  - Jump to specific position
DELETE /api/v1/transformations/datasets/{id}/history       - Clear history
```

See [API Documentation](API.md) for complete API reference.

## Related Documentation

- [Transformation History](../../claudedocs/TRANSFORMATION_HISTORY.md) - Undo/redo system
- [Versioning System](VERSIONING.md) - Version creation and management
- [Recipe System](RECIPE_SYSTEM.md) - Reusable transformation sequences
- [API Documentation](API.md) - REST API endpoints
- [Test Standards](TEST_STANDARDS.md) - Testing transformation code

## Configuration

### Environment Variables

```bash
# Transformation Settings
ENABLE_TRANSFORMATION_PREVIEW=true
PREVIEW_ROW_LIMIT=1000
MAX_TRANSFORMATION_TIME_SECONDS=300

# Performance
PARALLEL_PROCESSING_THRESHOLD_ROWS=100000
MAX_WORKERS=4

# Quality
WARN_ON_DATA_LOSS_PERCENT=10.0
FAIL_ON_DATA_LOSS_PERCENT=50.0
```

### Feature Flags

```python
ENABLE_AUTO_VERSIONING = True
ENABLE_TRANSFORMATION_CACHING = True
ENABLE_PARALLEL_EXECUTION = True
STRICT_VALIDATION_MODE = False
```
