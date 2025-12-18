# Data Issue Detection and Fix Suggestion System

## Overview

The Data Issue Detection system provides comprehensive data quality analysis with AI-powered insights and automated fix suggestions. It identifies common data quality issues, suggests appropriate fixes, and allows users to apply corrections individually or in batch.

## Features

### Issue Detection Types

| Issue Type | Description | Detection Method |
|------------|-------------|------------------|
| Missing Values | Null, NaN, or empty values | Rule-based |
| Outliers | Statistical anomalies | IQR or Z-score |
| Duplicates | Duplicate rows or values | Rule-based |
| Inconsistent Format | Format variations in same column | Pattern analysis |
| Type Mismatches | Values not matching column type | Rule-based |
| Inconsistent Casing | Mixed case variations | Pattern analysis |
| Whitespace Issues | Leading/trailing spaces | Rule-based |
| Date Format Issues | Inconsistent date formats | Pattern analysis |
| Semantic Issues | Context-inappropriate values | AI analysis |

### Severity Levels

- **Critical** (>50% affected): Requires immediate attention
- **High** (30-50% affected): Should be addressed soon
- **Medium** (10-30% affected): Worth investigating
- **Low** (<10% affected): Minor issues

## API Endpoints

### Detect Issues

```http
POST /api/v1/data-issues/detect
```

Triggers issue detection for a dataset.

**Request Body:**
```json
{
  "dataset_id": "string",
  "options": {
    "include_ai_analysis": true,
    "check_missing_values": true,
    "check_duplicates": true,
    "check_outliers": true,
    "check_inconsistencies": true,
    "check_type_mismatches": true,
    "outlier_method": "iqr",
    "outlier_threshold": 1.5,
    "columns": ["col1", "col2"],
    "sample_size": 10000
  }
}
```

**Response:**
```json
{
  "success": true,
  "dataset_id": "string",
  "issues": [...],
  "summary": {
    "total_issues": 5,
    "critical_count": 1,
    "high_count": 2,
    "medium_count": 1,
    "low_count": 1,
    "ai_detected_count": 2,
    "auto_fixable_count": 4,
    "detection_time_ms": 1234,
    "columns_analyzed": 10,
    "rows_analyzed": 1000
  },
  "record_id": "string"
}
```

### Get Dataset Issues

```http
GET /api/v1/data-issues/{dataset_id}/issues
```

Retrieves cached detection results.

**Query Parameters:**
- `include_ai`: Include AI-detected issues (default: true)
- `severity`: Filter by severity level

### Preview Fix

```http
POST /api/v1/data-issues/preview-fix
```

Preview a fix before applying it.

**Request Body:**
```json
{
  "dataset_id": "string",
  "issue_id": "string",
  "fix_id": "string",
  "preview_rows": 100
}
```

### Apply Fix

```http
POST /api/v1/data-issues/apply-fix
```

Apply a single fix to resolve an issue.

**Request Body:**
```json
{
  "dataset_id": "string",
  "issue_id": "string",
  "fix_id": "string",
  "preview_mode": false,
  "save_as_new_version": true
}
```

### Batch Apply Fixes

```http
POST /api/v1/data-issues/batch-fix
```

Apply multiple fixes in batch.

**Request Body:**
```json
{
  "dataset_id": "string",
  "issue_ids": ["id1", "id2", "id3"],
  "auto_apply_safe": true,
  "stop_on_error": true,
  "preview_mode": false
}
```

### Get Issue History

```http
GET /api/v1/data-issues/{dataset_id}/history
```

Retrieve detection history for a dataset.

## Architecture

### Component Flow

```
┌─────────────────┐     ┌──────────────────────┐
│   API Request   │────▶│ DataIssueDetection   │
│   /detect       │     │ Service              │
└─────────────────┘     └──────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
            ┌───────────┐  ┌───────────┐  ┌─────────────┐
            │Rule-based │  │ Outlier   │  │    AI       │
            │ Detection │  │ Detection │  │  Analyzer   │
            └─────┬─────┘  └─────┬─────┘  └──────┬──────┘
                  │              │               │
                  └──────────────┴───────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  FixSuggestionEngine   │
                    │  (generates fixes)     │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  TransformationEngine  │
                    │  (applies fixes)       │
                    └────────────────────────┘
```

### Key Services

1. **DataIssueDetectionService** (`app/services/data_issue_detection_service.py`)
   - Orchestrates issue detection
   - Combines rule-based and AI detection
   - Generates fix suggestions

2. **FixSuggestionEngine** (`app/services/fix_suggestion_engine.py`)
   - Maps issues to transformation types
   - Generates parameterized fixes
   - Applies fixes via TransformationEngine

3. **AIIssueAnalyzer** (`app/utils/ai_issue_analyzer.py`)
   - Privacy-safe data sampling
   - OpenAI-powered pattern detection
   - Semantic issue identification

## Detection Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `include_ai_analysis` | bool | true | Enable AI-powered detection |
| `check_missing_values` | bool | true | Check for null/empty values |
| `check_duplicates` | bool | true | Check for duplicate rows |
| `check_outliers` | bool | true | Detect statistical outliers |
| `check_inconsistencies` | bool | true | Check format/casing issues |
| `check_type_mismatches` | bool | true | Check type violations |
| `outlier_method` | str | "iqr" | Method: "iqr" or "zscore" |
| `outlier_threshold` | float | 1.5 | Threshold for outliers |
| `columns` | list | null | Specific columns to analyze |
| `sample_size` | int | null | Sample size for large datasets |

## Fix Types

| Transformation | Used For | Safety |
|----------------|----------|--------|
| `fill_missing_mean` | Missing numeric values | Safe |
| `fill_missing_median` | Missing numeric values | Safe |
| `fill_missing_mode` | Missing categorical values | Safe |
| `drop_rows_with_missing` | Missing values | Moderate |
| `remove_duplicates` | Duplicate rows | Safe |
| `trim_whitespace` | Whitespace issues | Safe |
| `standardize_case_lower` | Casing issues | Safe |
| `standardize_case_upper` | Casing issues | Safe |
| `standardize_case_title` | Casing issues | Safe |
| `clip_outliers` | Outliers | Moderate |
| `remove_outliers` | Outliers | Risky |

## Privacy & Security

### AI Analysis Privacy

- Only column statistics sent to AI (not raw data)
- Sensitive columns masked based on name patterns
- Maximum 100 sample rows analyzed
- PII patterns automatically detected and excluded

### Sensitive Column Detection

Columns matching these patterns are masked:
- Personal: name, email, phone, address
- Financial: account, credit, salary
- Medical: health, diagnosis, patient
- Identity: ssn, dob, age, gender

## Usage Examples

### Python (Backend)

```python
from app.services.data_issue_detection_service import DataIssueDetectionService
from app.schemas.data_issue import DetectionOptions

service = DataIssueDetectionService()

options = DetectionOptions(
    include_ai_analysis=True,
    check_outliers=True,
    outlier_method="iqr"
)

issues, summary = await service.detect_issues(
    df=dataframe,
    column_types={"col1": "integer", "col2": "string"},
    options=options,
    include_ai_analysis=True
)

# Apply a fix
fix_engine = FixSuggestionEngine()
result = await fix_engine.apply_fix(
    df=dataframe,
    issue=issues[0],
    suggested_fix=issues[0].suggested_fixes[0]
)
```

### TypeScript (Frontend)

```typescript
import { DataIssuesService } from '@/lib/services/data-issues';
import { useDataIssues } from '@/hooks/useDataIssues';

// Using the hook
const { issues, isLoading, detectIssues, applyFix } = useDataIssues(datasetId);

// Detect issues
await detectIssues({
  include_ai_analysis: true,
  check_outliers: true
});

// Apply a fix
await applyFix(issueId, fixId);
```

## Testing

Run the test suite:

```bash
cd apps/backend
uv run pytest tests/test_services/test_data_issue_detection.py -v
uv run pytest tests/test_services/test_fix_suggestion_engine.py -v
```

Test coverage includes:
- Missing value detection
- Outlier detection (IQR and Z-score)
- Whitespace and casing issues
- Severity calculation
- Fix suggestion generation
- Batch fix operations
- Edge cases (empty data, clean data)

## Error Handling

The system handles various error conditions:

- **Empty Dataset**: Returns empty results with success=true
- **Invalid Column Types**: Skips problematic columns
- **AI Failure**: Falls back to rule-based detection only
- **Fix Application Errors**: Reports individual failures in batch operations

## Performance Considerations

- Large datasets (>10,000 rows) automatically sampled
- AI analysis limited to 100 rows max
- Detection results cached in MongoDB
- Batch operations optimized for throughput
