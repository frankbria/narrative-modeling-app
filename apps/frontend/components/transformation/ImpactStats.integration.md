# ImpactStats Integration Guide

This guide demonstrates how to integrate the `ImpactStats` component into your transformation workflows.

## Quick Start

### Import the Component

```typescript
// Direct import
import { ImpactStats } from '@/components/transformation/ImpactStats';

// Or from the index export
import { ImpactStats, type ImpactStatsProps } from '@/components/transformation';
```

### Basic Usage

```typescript
'use client';

import { ImpactStats } from '@/components/transformation';

export function TransformationResults() {
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

## Integration with TransformationPreview

The `ImpactStats` component is designed to work seamlessly with the existing `TransformationPreview` component.

### Using PreviewResult.impact_statistics

```typescript
import { TransformationPreview, ImpactStats } from '@/components/transformation';

export function TransformationWorkflow() {
  const [previewResult, setPreviewResult] = useState<PreviewResult | null>(null);

  return (
    <div className="space-y-6">
      <TransformationPreview
        datasetId="dataset-123"
        transformations={[
          { type: 'standardize', columns: ['name', 'email'] },
          { type: 'fill_missing', columns: ['age'], method: 'mean' },
        ]}
        onPreviewComplete={(result) => setPreviewResult(result)}
      />

      {previewResult?.impact_statistics && (
        <ImpactStats impactStats={previewResult.impact_statistics} />
      )}
    </div>
  );
}
```

## Integration with TransformationConfigDialog

The dialog can pass impact statistics to the ImpactStats component:

```typescript
import {
  TransformationConfigDialog,
  ImpactStats,
  type TransformationConfig,
} from '@/components/transformation';
import { useState } from 'react';

export function ConfigWithImpact() {
  const [impactStats, setImpactStats] = useState(null);
  const [showImpact, setShowImpact] = useState(false);

  const handleTransformationApply = async (config: TransformationConfig) => {
    try {
      const response = await fetch('/api/transformations/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      const data = await response.json();
      setImpactStats(data.impact_statistics);
      setShowImpact(true);
    } catch (error) {
      console.error('Failed to apply transformation:', error);
    }
  };

  return (
    <>
      <TransformationConfigDialog
        onApply={handleTransformationApply}
        datasetId="dataset-123"
      />

      {showImpact && impactStats && (
        <div className="mt-8 p-4 bg-white rounded-lg border">
          <ImpactStats impactStats={impactStats} />
        </div>
      )}
    </>
  );
}
```

## Integration with TransformationChainView

Use ImpactStats to show the cumulative impact of a transformation chain:

```typescript
import {
  TransformationChainView,
  ImpactStats,
} from '@/components/transformation';
import { useState } from 'react';

export function ChainWithImpact() {
  const [cumulativeImpact, setCumulativeImpact] = useState(null);

  const handleChainApply = async (chain) => {
    const response = await fetch('/api/transformations/chain/apply', {
      method: 'POST',
      body: JSON.stringify({ chain }),
    });

    const data = await response.json();
    setCumulativeImpact(data.cumulative_impact);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div>
        <h2 className="text-2xl font-bold mb-4">Transformation Chain</h2>
        <TransformationChainView onApply={handleChainApply} />
      </div>

      <div>
        <h2 className="text-2xl font-bold mb-4">Cumulative Impact</h2>
        {cumulativeImpact && (
          <ImpactStats impactStats={cumulativeImpact} />
        )}
      </div>
    </div>
  );
}
```

## API Integration Patterns

### Pattern 1: Async Transformation with Impact

```typescript
async function applyTransformationWithImpact(
  datasetId: string,
  transformations: TransformationConfig[]
): Promise<ImpactStatistics> {
  const response = await fetch('/api/datasets/{datasetId}/transform', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getAuthToken()}`,
    },
    body: JSON.stringify({
      transformations,
      includeImpactAnalysis: true,
    }),
  });

  if (!response.ok) {
    throw new Error(`Transformation failed: ${response.statusText}`);
  }

  const data = await response.json();
  return data.impact_statistics;
}

// Usage
export function ApplyTransformation() {
  const [loading, setLoading] = useState(false);
  const [impact, setImpact] = useState<ImpactStatistics | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleApply = async () => {
    setLoading(true);
    setError(null);

    try {
      const stats = await applyTransformationWithImpact('dataset-123', [
        { type: 'standardize', columns: ['email'] },
      ]);
      setImpact(stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <button
        onClick={handleApply}
        disabled={loading}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Applying...' : 'Apply Transformation'}
      </button>

      {error && (
        <div className="p-4 bg-red-100 text-red-800 rounded-lg">{error}</div>
      )}

      {impact && <ImpactStats impactStats={impact} />}
    </div>
  );
}
```

### Pattern 2: Streaming Impact Updates

```typescript
async function* streamTransformationImpact(
  datasetId: string,
  transformations: TransformationConfig[]
) {
  const response = await fetch('/api/datasets/{datasetId}/transform/stream', {
    method: 'POST',
    body: JSON.stringify({ transformations }),
  });

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.trim()) {
        try {
          yield JSON.parse(line) as ImpactStatistics;
        } catch (e) {
          console.error('Failed to parse streamed update:', e);
        }
      }
    }
  }
}

// Usage with live updates
export function StreamingTransformation() {
  const [impact, setImpact] = useState<ImpactStatistics | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const handleStream = async () => {
    setIsStreaming(true);

    try {
      for await (const update of streamTransformationImpact('dataset-123', [
        { type: 'standardize', columns: ['name'] },
      ])) {
        setImpact(update);
      }
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="space-y-4">
      <button
        onClick={handleStream}
        disabled={isStreaming}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        {isStreaming ? 'Streaming...' : 'Start Stream'}
      </button>

      {impact && <ImpactStats impactStats={impact} />}
    </div>
  );
}
```

## Advanced Scenarios

### Scenario 1: Multi-Step Transformation Tracking

Track impact at each step of a complex transformation:

```typescript
export function MultiStepTransformation() {
  const [steps, setSteps] = useState<
    Array<{ step: string; impact: ImpactStatistics }>
  >([]);

  const applySteps = async (transformations: TransformationConfig[]) => {
    const results = [];

    for (let i = 0; i < transformations.length; i++) {
      const step = transformations.slice(0, i + 1);
      const response = await fetch('/api/transformations/preview', {
        method: 'POST',
        body: JSON.stringify({ transformations: step }),
      });

      const data = await response.json();
      results.push({
        step: `Step ${i + 1}: ${transformations[i].type}`,
        impact: data.impact_statistics,
      });
    }

    setSteps(results);
  };

  return (
    <div className="space-y-6">
      {steps.map((item, idx) => (
        <div key={idx} className="space-y-2">
          <h3 className="text-lg font-semibold">{item.step}</h3>
          <ImpactStats impactStats={item.impact} />
        </div>
      ))}
    </div>
  );
}
```

### Scenario 2: Impact Comparison

Compare impact of different transformation strategies:

```typescript
export function ImpactComparison() {
  const [results, setResults] = useState<Record<string, ImpactStatistics>>({});

  const compareStrategies = async () => {
    const strategies = {
      'Mean Imputation': [{ type: 'fill_missing', method: 'mean' }],
      'Median Imputation': [{ type: 'fill_missing', method: 'median' }],
      'Forward Fill': [{ type: 'fill_missing', method: 'forward' }],
    };

    const comparisons: Record<string, ImpactStatistics> = {};

    for (const [name, transforms] of Object.entries(strategies)) {
      const response = await fetch('/api/transformations/preview', {
        method: 'POST',
        body: JSON.stringify({ transformations: transforms }),
      });

      const data = await response.json();
      comparisons[name] = data.impact_statistics;
    }

    setResults(comparisons);
  };

  return (
    <div className="space-y-6">
      <button
        onClick={compareStrategies}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg"
      >
        Compare Strategies
      </button>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(results).map(([strategy, impact]) => (
          <div key={strategy} className="border rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-4">{strategy}</h3>
            <ImpactStats impactStats={impact} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Scenario 3: Conditional Display Based on Impact

Show warnings or confirmations based on transformation impact:

```typescript
export function ConditionalImpactDisplay() {
  const [impact, setImpact] = useState<ImpactStatistics | null>(null);
  const [showWarning, setShowWarning] = useState(false);

  useEffect(() => {
    if (!impact) return;

    // Show warning if quality degrades by more than 5%
    const qualityChange = impact.quality_score_after - impact.quality_score_before;
    if (qualityChange < -0.05) {
      setShowWarning(true);
    }

    // Show warning if many rows affected
    if (impact.rows_affected > 50000) {
      setShowWarning(true);
    }
  }, [impact]);

  return (
    <div className="space-y-4">
      {showWarning && (
        <div className="p-4 bg-yellow-100 text-yellow-800 rounded-lg border border-yellow-300">
          Warning: This transformation has significant impact on your data.
          Please review the statistics below carefully before confirming.
        </div>
      )}

      {impact && <ImpactStats impactStats={impact} />}

      {impact && (
        <div className="flex gap-4">
          <button className="px-4 py-2 bg-green-600 text-white rounded-lg">
            Confirm & Apply
          </button>
          <button className="px-4 py-2 bg-gray-400 text-white rounded-lg">
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
```

## Type Definitions

```typescript
// From your API response
interface TransformationResponse {
  success: boolean;
  dataset_id: string;
  impact_statistics: ImpactStatistics;
  transformation_id: string;
  timestamp: string;
}

// Component props
interface ImpactStatsProps {
  impactStats: ImpactStatistics;
}

// Statistics structure
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

## Error Handling

Implement proper error boundaries around ImpactStats:

```typescript
import { ErrorBoundary } from 'react-error-boundary';
import { ImpactStats } from '@/components/transformation';

function ImpactStatsErrorFallback({
  error,
  resetErrorBoundary,
}: {
  error: Error;
  resetErrorBoundary: () => void;
}) {
  return (
    <div className="p-4 bg-red-100 text-red-800 rounded-lg">
      <h2 className="font-semibold">Failed to display impact statistics</h2>
      <p className="text-sm mt-2">{error.message}</p>
      <button
        onClick={resetErrorBoundary}
        className="mt-2 px-3 py-1 bg-red-600 text-white rounded"
      >
        Try Again
      </button>
    </div>
  );
}

export function SafeImpactStats({ impactStats }: ImpactStatsProps) {
  return (
    <ErrorBoundary FallbackComponent={ImpactStatsErrorFallback}>
      <ImpactStats impactStats={impactStats} />
    </ErrorBoundary>
  );
}
```

## Performance Optimization

For large datasets, optimize rendering:

```typescript
import { useMemo } from 'react';
import { ImpactStats } from '@/components/transformation';

export function OptimizedImpactStats({ impactStats }: ImpactStatsProps) {
  const memoizedStats = useMemo(() => impactStats, [impactStats]);

  return <ImpactStats impactStats={memoizedStats} />;
}
```

## Testing Integration

```typescript
import { render, screen } from '@testing-library/react';
import { ImpactStats } from '@/components/transformation';

describe('ImpactStats Integration', () => {
  it('should display API response data correctly', () => {
    const apiResponse = {
      rows_affected: 5000,
      values_changed: 12500,
      columns_affected: ['col1', 'col2', 'col3'],
      quality_score_before: 0.65,
      quality_score_after: 0.91,
    };

    render(<ImpactStats impactStats={apiResponse} />);

    expect(screen.getByText('5,000')).toBeInTheDocument();
    expect(screen.getByText('65%')).toBeInTheDocument();
    expect(screen.getByText('91%')).toBeInTheDocument();
  });
});
```

## Next Steps

1. **Integrate with your transformation API endpoints**
2. **Add error handling for failed transformations**
3. **Implement confirmation dialogs for high-impact changes**
4. **Add export/reporting functionality**
5. **Create dashboard views showing transformation history**
