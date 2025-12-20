# ImpactStats Quick Start Guide

## Installation & Import

```typescript
// Import the component
import { ImpactStats } from '@/components/transformation';

// Or direct import
import { ImpactStats } from '@/components/transformation/ImpactStats';
```

## 30-Second Example

```typescript
'use client';
import { ImpactStats } from '@/components/transformation';

export function MyComponent() {
  const impactStats = {
    rows_affected: 1250,
    values_changed: 3847,
    columns_affected: ['name', 'email', 'age'],
    quality_score_before: 0.72,
    quality_score_after: 0.88,
  };

  return <ImpactStats impactStats={impactStats} />;
}
```

## What You Get

A dashboard showing:
1. **Rows Affected** - Count of modified rows
2. **Values Changed** - Total cells modified
3. **Columns Affected** - List of affected columns
4. **Quality Score** - Before/after comparison with visual bars
5. **Optional Distribution** - Value changes per column (if provided)

## Minimum Props

```typescript
impactStats: {
  rows_affected: number;           // e.g., 1250
  values_changed: number;          // e.g., 3847
  columns_affected: string[];      // e.g., ['col1', 'col2']
  quality_score_before: number;    // 0.0 to 1.0
  quality_score_after: number;     // 0.0 to 1.0
}
```

## Optional Props

```typescript
impactStats: {
  // ... minimum props above ...
  value_distributions?: {           // Optional
    "column_name": {
      before: { "value": count, ... },
      after: { "value": count, ... }
    },
    // ... more columns ...
  }
}
```

## Real-World Example

```typescript
// After transformation API call
const response = await fetch('/api/transform', { method: 'POST', ... });
const data = await response.json();

// Use the response directly
<ImpactStats impactStats={data.impact_statistics} />
```

## Visual Features

- **Color-coded improvements**: Green for better, red for worse, blue for neutral
- **Progress bars**: Visual representation of quality scores
- **Expandable sections**: Click to view detailed value distributions
- **Responsive layout**: Adapts from mobile (1 col) to desktop (3 cols)
- **Formatted numbers**: Automatic comma separators for large numbers

## Common Patterns

### Pattern 1: Show Results After Transformation
```typescript
const [impact, setImpact] = useState(null);

const handleApply = async () => {
  const result = await applyTransformation();
  setImpact(result.impact_statistics);
};

return impact ? <ImpactStats impactStats={impact} /> : null;
```

### Pattern 2: Display in Modal
```typescript
<Dialog open={showResults}>
  <DialogContent>
    <ImpactStats impactStats={transformationResult} />
  </DialogContent>
</Dialog>
```

### Pattern 3: Compare Multiple Strategies
```typescript
{strategies.map((strategy) => (
  <div key={strategy.id}>
    <h3>{strategy.name}</h3>
    <ImpactStats impactStats={strategy.impact} />
  </div>
))}
```

## Quality Score Interpretation

- **90-100%**: Excellent quality
- **70-89%**: Good quality
- **50-69%**: Fair quality
- **Below 50%**: Poor quality

Green badge = improvement
Red badge = degradation

## Tips & Best Practices

1. **Always provide quality scores** - They're essential for impact assessment
2. **Include distributions** - For 3+ affected columns, distributions help analysis
3. **Wrap in error boundary** - Handle malformed data gracefully
4. **Show early** - Display impact before applying transformations
5. **Confirm large impacts** - Warn users if many rows are affected

## Troubleshooting

### Component doesn't display?
- Check imports: `from '@/components/transformation'`
- Verify parent has `'use client'` directive
- Ensure impactStats prop is provided

### Numbers look wrong?
- Quality scores should be 0-1 (not percentages)
- Verify API response format matches expected structure

### Distribution not showing?
- Check `value_distributions` object has entries
- Ensure distributions are provided in props
- Click to expand the section

## Related Documentation

- Full docs: `/components/transformation/IMPACT_STATS.md`
- Integration guide: `/components/transformation/ImpactStats.integration.md`
- Examples: `/components/transformation/ImpactStats.example.tsx`
- Tests: `/__tests__/components/transformation/ImpactStats.test.tsx`
