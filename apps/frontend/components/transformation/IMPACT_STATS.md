# ImpactStats Component Documentation

## Overview

The `ImpactStats` component is a dashboard widget that displays the statistical impact of data transformations. It provides a comprehensive view of how transformations affect data quality, structure, and content through visual metrics and detailed statistics.

## Location

`apps/frontend/components/transformation/ImpactStats.tsx`

## Features

### Core Metrics Display
- **Rows Affected**: Number of rows with changes
- **Values Changed**: Total count of cells modified
- **Columns Affected**: List of column names affected
- **Quality Score Comparison**: Before/after visualization with progress bars

### Visual Indicators
- **Color-coded Quality Changes**:
  - Green: Quality improvement
  - Red: Quality degradation
  - Blue: No change or neutral
- **Trend Icons**: Up/down arrows indicating improvement/degradation
- **Progress Bars**: Visual representation of quality scores
- **Badges**: Percentage change indicators

### Optional Features
- **Value Distribution Analysis**: Expandable section showing before/after value distributions for affected columns
- **Distribution Visualizations**: Mini bar charts showing value frequency changes
- **Responsive Grid Layout**: Adapts from 1 column on mobile to 3 columns on desktop

## Props Interface

```typescript
interface ImpactStatsProps {
  impactStats: ImpactStatistics;
}

interface ImpactStatistics {
  rows_affected: number;
  values_changed: number;
  columns_affected: string[];
  quality_score_before: number;
  quality_score_after: number;
  value_distributions?: Record<
    string,
    { before: Record<string, number>; after: Record<string, number> }
  >;
}
```

### Props Description

#### `impactStats` (Required)
An object containing transformation impact metrics:

- **`rows_affected`** (number): Count of rows that were modified by the transformation
- **`values_changed`** (number): Total count of individual cell values that changed
- **`columns_affected`** (string[]): Array of column names that were modified
- **`quality_score_before`** (number): Quality score before transformation (0-1 scale)
- **`quality_score_after`** (number): Quality score after transformation (0-1 scale)
- **`value_distributions`** (optional): Object mapping column names to before/after value distributions
  - Each value is an object with `before` and `after` properties
  - `before`/`after` are objects mapping values to their counts

## Usage Examples

### Basic Usage

```typescript
import { ImpactStats } from '@/components/transformation/ImpactStats';

export function TransformationResultsPage() {
  const impactStats = {
    rows_affected: 1250,
    values_changed: 3847,
    columns_affected: ['age', 'salary', 'department'],
    quality_score_before: 0.72,
    quality_score_after: 0.88,
  };

  return <ImpactStats impactStats={impactStats} />;
}
```

### With Value Distributions

```typescript
const impactStats = {
  rows_affected: 5000,
  values_changed: 12500,
  columns_affected: ['status', 'category'],
  quality_score_before: 0.65,
  quality_score_after: 0.91,
  value_distributions: {
    status: {
      before: {
        'Active': 3000,
        'Inactive': 1500,
        'Pending': 500,
      },
      after: {
        'Active': 3500,
        'Inactive': 1200,
        'Pending': 300,
      },
    },
    category: {
      before: {
        'A': 1500,
        'B': 2000,
        'C': 1500,
      },
      after: {
        'A': 1800,
        'B': 2100,
        'C': 1100,
      },
    },
  },
};

return <ImpactStats impactStats={impactStats} />;
```

## Component Structure

### Layout Sections

1. **Title Section**
   - "Impact Statistics" heading

2. **Metrics Cards Grid** (3 columns on desktop, 1 on mobile)
   - Rows Affected Card
   - Values Changed Card
   - Columns Affected Card

3. **Quality Score Comparison Card**
   - Before/after progress bars
   - Trend indicator (↑/→/↓)
   - Change percentage badge

4. **Value Distribution Changes** (Optional, Expandable)
   - Collapsible section per column
   - Before/after distribution comparison
   - Mini bar charts for visual comparison

## Styling

The component uses:
- **Tailwind CSS** for layout and responsive design
- **Shadcn/UI components**: Card, Progress, Badge
- **Lucide React icons**: ChevronDown, TrendingUp, TrendingDown
- **Color scheme**:
  - Blue: Neutral/baseline (bg-blue-500, bg-blue-400)
  - Green: Improvement (bg-green-500, bg-green-400, text-green-800)
  - Red: Degradation (bg-red-500, text-red-800)
  - Gray: Secondary text and borders

## Responsive Behavior

```
Desktop (md and up):
- Metrics: 3 columns grid
- Distributions: 2 columns for before/after

Mobile (sm and below):
- Metrics: 1 column stack
- Distributions: 1 column stack (before/after vertically aligned)
```

## Key Implementation Details

### Quality Score Calculation
- Change is calculated as: `quality_score_after - quality_score_before`
- Absolute value is used for percentage display: `Math.abs(qualityChange) * 100`
- Direction is determined by sign of change

### Distribution Display
- Shows top 5 values per distribution (+ count indicator for remaining)
- Uses proportional bar widths based on max count
- Separate scaling for before/after to allow comparison
- Blue bars for before, green bars for after

### State Management
- Uses single `expandedDistributions` state for expandable section
- Simple toggle on button click

### Performance Considerations
- All calculations are O(n) where n is number of values in distributions
- No expensive re-renders on data changes
- Memoization recommended for parent component if `impactStats` changes frequently

## Accessibility Features

- Semantic HTML with proper heading hierarchy
- Color-coded information also includes text labels
- Icons paired with descriptive text
- ARIA-compliant button for expansion

## Testing Recommendations

### Unit Tests
```typescript
describe('ImpactStats', () => {
  it('should display rows affected correctly', () => {
    const impactStats = {
      rows_affected: 1250,
      values_changed: 3847,
      columns_affected: ['col1'],
      quality_score_before: 0.72,
      quality_score_after: 0.88,
    };

    render(<ImpactStats impactStats={impactStats} />);
    expect(screen.getByText('1,250')).toBeInTheDocument();
  });

  it('should show quality improvement badge', () => {
    // Test quality improvement indicator
  });

  it('should expand/collapse distributions', () => {
    // Test expandable section behavior
  });

  it('should render distributions correctly', () => {
    // Test distribution rendering with proper counts
  });
});
```

### Integration Tests
- Test with real transformation API responses
- Verify responsive layout on different screen sizes
- Test with large datasets (100+ value distributions)

## Integration Points

### Backend API Response Format
The component expects responses matching this structure:

```json
{
  "impact_statistics": {
    "rows_affected": 1250,
    "values_changed": 3847,
    "columns_affected": ["age", "salary"],
    "quality_score_before": 0.72,
    "quality_score_after": 0.88,
    "value_distributions": {
      "age": {
        "before": {"0-18": 100, "18-30": 200},
        "after": {"0-18": 105, "18-30": 195}
      }
    }
  }
}
```

### Common Parent Components
- `TransformationPipeline.tsx`: Workflow orchestration
- `TransformationConfigDialog.tsx`: Configuration and preview
- `TransformationChainView.tsx`: Visual pipeline editor

## Common Scenarios

### Data Standardization
```typescript
const standardizationImpact = {
  rows_affected: 50000,
  values_changed: 125000,
  columns_affected: ['name', 'email', 'phone'],
  quality_score_before: 0.45,
  quality_score_after: 0.95,
};
```

### Handling Missing Values
```typescript
const missingValueImpact = {
  rows_affected: 15000,
  values_changed: 25000,
  columns_affected: ['age', 'salary', 'department'],
  quality_score_before: 0.68,
  quality_score_after: 0.85,
};
```

### Data Type Conversion
```typescript
const conversionImpact = {
  rows_affected: 8000,
  values_changed: 8000,
  columns_affected: ['date_column', 'numeric_column'],
  quality_score_before: 0.82,
  quality_score_after: 0.88,
};
```

## Error Handling

The component assumes:
- `rows_affected` and `values_changed` are non-negative integers
- Quality scores are between 0 and 1
- Column names in `columns_affected` are strings
- Distributions are properly formatted with numeric counts

**Note**: No explicit error boundaries are implemented. Add error handling in parent components if needed.

## Performance Guidelines

- **Safe for**: Datasets with up to 100 distribution entries
- **Recommended max**: 10 columns with 20+ top values each
- **Optimization**: Use `React.memo()` if parent re-renders frequently

## Future Enhancements

Potential improvements:
1. Add chart library integration (recharts) for distribution visualizations
2. Export transformation impact as CSV/PDF report
3. Compare multiple transformation runs side-by-side
4. Add drill-down capability for value distributions
5. Implement undo/rollback for transformations
6. Add animation transitions for score changes

## Related Components

- `StatsCard.tsx`: General statistics display for data fields
- `QualityReportCard.tsx`: Overall quality assessment
- `TransformationChainView.tsx`: Visual transformation pipeline
- `TransformationConfigDialog.tsx`: Configuration UI

## Version History

- **v1.0.0** (2025-12-19): Initial implementation
  - Core metrics display
  - Quality score comparison
  - Expandable value distributions
  - Responsive layout
  - Color-coded quality indicators
