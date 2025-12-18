# Developer Guide: Data Issue Detection

This guide covers implementation details for developers extending or maintaining the Data Issue Detection system.

## Architecture Overview

```
apps/backend/
├── app/
│   ├── models/
│   │   └── data_issue.py          # Domain models
│   ├── schemas/
│   │   └── data_issue.py          # API schemas
│   ├── services/
│   │   ├── data_issue_detection_service.py
│   │   └── fix_suggestion_engine.py
│   ├── utils/
│   │   └── ai_issue_analyzer.py
│   └── api/routes/
│       └── data_issues.py
└── tests/test_services/
    ├── test_data_issue_detection.py
    └── test_fix_suggestion_engine.py

apps/frontend/
├── lib/services/
│   └── data-issues.ts             # API client
├── hooks/
│   └── useDataIssues.ts           # React hook
└── components/data-issues/
    ├── DataIssueDetector.tsx      # Main component
    ├── IssueList.tsx
    ├── FixSuggestionCard.tsx
    ├── BatchFixPanel.tsx
    └── IssueSeverityBadge.tsx
```

## Adding New Issue Types

### 1. Add to IssueType Enum

```python
# app/models/data_issue.py
class IssueType(str, Enum):
    # ... existing types
    NEW_ISSUE_TYPE = "new_issue_type"
```

### 2. Implement Detection Logic

```python
# app/services/data_issue_detection_service.py
async def _detect_new_issue_type(
    self,
    df: pd.DataFrame,
    column_types: Dict[str, str]
) -> List[DataIssue]:
    issues = []

    for col in df.columns:
        # Your detection logic here
        if self._has_issue(df[col]):
            affected = self._count_affected(df[col])
            pct = (affected / len(df)) * 100

            issues.append(DataIssue(
                issue_type=IssueType.NEW_ISSUE_TYPE,
                severity=self._get_severity_from_percentage(pct),
                affected_column=col,
                affected_rows=affected,
                affected_percentage=pct,
                description=f"Description of issue in {col}",
                impact="How this affects analysis",
                suggested_fixes=self._get_fixes_for_new_issue(col, df)
            ))

    return issues
```

### 3. Add Fix Mappings

```python
# app/services/fix_suggestion_engine.py
ISSUE_FIX_MAPPINGS = {
    # ... existing mappings
    IssueType.NEW_ISSUE_TYPE: [
        "transformation_type_1",
        "transformation_type_2"
    ]
}
```

### 4. Update Frontend Labels

```typescript
// lib/services/data-issues.ts
export function getIssueTypeLabel(issueType: string): string {
  const labels: Record<string, string> = {
    // ... existing labels
    new_issue_type: 'New Issue Type',
  };
  return labels[issueType] || issueType;
}
```

### 5. Add Tests

```python
# tests/test_services/test_data_issue_detection.py
@pytest.mark.asyncio
async def test_detect_new_issue_type(self, service):
    """Test detection of new issue type."""
    df = pd.DataFrame({
        'col': [/* data that triggers the issue */]
    })

    options = DetectionOptions(
        check_new_issues=True,  # Add option if needed
        include_ai_analysis=False
    )

    issues, summary = await service.detect_issues(
        df, {'col': 'string'}, options, include_ai_analysis=False
    )

    new_issues = [i for i in issues if i.issue_type == IssueType.NEW_ISSUE_TYPE]
    assert len(new_issues) >= 1
```

## Adding New Fix Types

### 1. Add Transformation Type

```python
# Ensure the transformation exists in TransformationEngine
# or add a new transformation type

# app/services/fix_suggestion_engine.py
def _generate_fix_for_transformation(
    self,
    transformation_type: str,
    issue: DataIssue,
    df: pd.DataFrame
) -> SuggestedFix:
    if transformation_type == "new_fix_type":
        return SuggestedFix(
            transformation_type="new_fix_type",
            parameters={"param1": "value1"},
            explanation="What this fix does",
            ai_generated=False,
            confidence_score=0.9,
            estimated_rows_affected=issue.affected_rows,
            estimated_data_loss=0.0,
            is_safe=True
        )
```

### 2. Update Safety Classifications

```python
# app/services/fix_suggestion_engine.py
SAFE_TRANSFORMATIONS = [
    # ... existing
    "new_fix_type"  # If safe
]

MODERATE_TRANSFORMATIONS = [
    # ... existing
    "new_fix_type"  # If moderate risk
]
```

## AI Analyzer Extension

### Adding New Analysis Patterns

```python
# app/utils/ai_issue_analyzer.py
async def _call_openai_analysis(
    self,
    sample_data: Dict[str, Any],
    column_types: Dict[str, str],
    existing_issues: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:

    # Extend the system prompt for new patterns
    system_prompt = """..existing prompt...

    Also check for:
    - New pattern type 1
    - New pattern type 2
    """
```

### Privacy-Safe Sampling

To add new sensitive column patterns:

```python
# app/utils/ai_issue_analyzer.py
def _is_potentially_sensitive(self, column_name: str) -> bool:
    sensitive_patterns = [
        # ... existing patterns
        'new_sensitive_pattern',
    ]
```

## Frontend Component Extension

### Custom Issue Renderer

```tsx
// components/data-issues/CustomIssueCard.tsx
import { DataIssue } from '@/lib/services/data-issues';

interface CustomIssueCardProps {
  issue: DataIssue;
  onFix: (issueId: string, fixId: string) => void;
}

export function CustomIssueCard({ issue, onFix }: CustomIssueCardProps) {
  // Custom rendering logic
  return (
    <Card>
      {/* Custom UI */}
    </Card>
  );
}
```

### Extending the Hook

```typescript
// hooks/useDataIssues.ts
export function useDataIssues(datasetId: string | null) {
  // ... existing state

  // Add custom functionality
  const customAction = useCallback(async () => {
    // Custom logic
  }, [datasetId]);

  return {
    // ... existing returns
    customAction,
  };
}
```

## Testing Guidelines

### Unit Test Structure

```python
class TestNewFeature:
    @pytest.fixture
    def service(self):
        return DataIssueDetectionService()

    @pytest.fixture
    def sample_data(self):
        return pd.DataFrame({...})

    @pytest.mark.asyncio
    async def test_feature_behavior(self, service, sample_data):
        # Arrange
        options = DetectionOptions(...)

        # Act
        issues, summary = await service.detect_issues(...)

        # Assert
        assert len(issues) == expected_count
```

### Mocking AI Analyzer

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mocked_ai(self, service):
    mock_issues = [
        DataIssue(
            issue_type=IssueType.INVALID_VALUES,
            severity=IssueSeverity.MEDIUM,
            # ... other fields
        )
    ]

    with patch.object(
        service.ai_analyzer,
        'analyze_data_patterns',
        new_callable=AsyncMock,
        return_value=mock_issues
    ):
        issues, summary = await service.detect_issues(
            df, column_types, options, include_ai_analysis=True
        )

        assert summary.ai_detected_count == 1
```

## Common Patterns

### Severity Calculation

```python
def _get_severity_from_percentage(self, percentage: float) -> IssueSeverity:
    if percentage > 50:
        return IssueSeverity.CRITICAL
    elif percentage > 30:
        return IssueSeverity.HIGH
    elif percentage > 10:
        return IssueSeverity.MEDIUM
    else:
        return IssueSeverity.LOW
```

### Error Handling

```python
async def detect_issues(self, df, column_types, options, include_ai_analysis):
    try:
        # Detection logic
        pass
    except Exception as e:
        logger.error(f"Detection failed: {str(e)}")
        # Return empty results on failure
        return [], DetectionSummary(
            total_issues=0,
            columns_analyzed=len(df.columns),
            rows_analyzed=len(df),
            detection_time_ms=0
        )
```

### DataFrame Type Safety

```python
def _safe_numeric_operation(self, series: pd.Series) -> Optional[float]:
    try:
        numeric = pd.to_numeric(series, errors='coerce')
        if numeric.isna().all():
            return None
        return float(numeric.mean())
    except Exception:
        return None
```

## Performance Optimization

### Sampling Large Datasets

```python
def _sample_if_needed(
    self,
    df: pd.DataFrame,
    sample_size: Optional[int]
) -> pd.DataFrame:
    if sample_size and len(df) > sample_size:
        return df.sample(n=sample_size, random_state=42)
    return df
```

### Caching Results

```python
# Use MongoDB for caching detection results
async def _cache_results(
    self,
    dataset_id: str,
    user_id: str,
    issues: List[DataIssue],
    summary: DetectionSummary
) -> str:
    record = DataIssueRecord(
        dataset_id=dataset_id,
        user_id=user_id,
        detection_options={},
        issues=issues,
        summary=summary,
        applied_fixes=[]
    )
    await record.insert()
    return str(record.id)
```

## Debugging Tips

### Enable Debug Logging

```python
import logging
logging.getLogger('app.services.data_issue_detection_service').setLevel(logging.DEBUG)
```

### Inspect Intermediate Results

```python
# Add debugging in service
async def detect_issues(self, ...):
    logger.debug(f"Starting detection for {len(df)} rows, {len(df.columns)} columns")

    rule_issues = await self._detect_rule_based_issues(df, column_types, options)
    logger.debug(f"Rule-based detection found {len(rule_issues)} issues")

    ai_issues = await self._detect_ai_issues(df, column_types, rule_issues)
    logger.debug(f"AI detection found {len(ai_issues)} additional issues")
```

## Circuit Breaker Configuration

```python
# app/utils/ai_issue_analyzer.py
@with_circuit_breaker(
    "openai_issue_analyzer",
    max_attempts=3,           # Retry attempts
    failure_threshold=5,      # Failures before opening
    recovery_timeout=60.0,    # Seconds before retry
    exceptions=(OpenAIError, Exception),
    fallback_value=None       # Return on failure
)
async def _call_openai_analysis(self, ...):
    pass
```

## Related Documentation

- [DATA_ISSUE_DETECTION.md](./DATA_ISSUE_DETECTION.md) - Feature overview
- [TDD_GUIDE.md](./TDD_GUIDE.md) - Testing methodology
- [TEST_INFRASTRUCTURE.md](./TEST_INFRASTRUCTURE.md) - Test setup
