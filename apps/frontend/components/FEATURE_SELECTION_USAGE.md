# Feature Selection Components - Usage Guide

## Overview

The feature selection system provides a comprehensive UI for selecting the most important features from your dataset using multiple selection algorithms.

## Components

### 1. FeatureSelection (Main Component)

The main orchestrator component that manages the entire feature selection workflow.

```tsx
import { FeatureSelection } from '@/components/FeatureSelection'

function DatasetPage() {
  return (
    <FeatureSelection
      datasetId="dataset_abc123"
      columns={['age', 'income', 'education', 'target']}
      defaultTargetColumn="target"
      onComplete={(result) => {
        console.log('Selected features:', result.selected_features)
      }}
    />
  )
}
```

**Props:**
- `datasetId: string` - The dataset identifier
- `columns: string[]` - Array of column names from the dataset
- `defaultTargetColumn?: string` - Pre-select a target column
- `onComplete?: (result) => void` - Callback when selection completes

### 2. SelectionControls

Configuration UI for feature selection parameters.

```tsx
import { SelectionControls } from '@/components/SelectionControls'

const [config, setConfig] = useState({
  method: 'correlation',
  targetColumn: 'target',
  topK: 10,
  correlationThreshold: 0.7
})

<SelectionControls
  config={config}
  onChange={setConfig}
  onRunSelection={handleRun}
  onCompare={handleCompare}
  columns={columns}
  isLoading={false}
/>
```

### 3. FeatureImportanceChart

Horizontal bar chart displaying feature importance scores.

```tsx
import { FeatureImportanceChart } from '@/components/FeatureImportanceChart'

<FeatureImportanceChart
  features={result.feature_scores}
  height={500}
  showOnlySelected={false}
  onFeatureClick={(feature) => console.log('Clicked:', feature.feature_name)}
  highlightThreshold={0.5}
/>
```

### 4. SelectedFeatureSet

Summary card showing selected features with export capabilities.

```tsx
import { SelectedFeatureSet } from '@/components/SelectedFeatureSet'

<SelectedFeatureSet
  result={selectionResult}
  onExportJSON={() => console.log('Export JSON')}
  onExportCSV={() => console.log('Export CSV')}
  onProceedToModeling={() => router.push('/train')}
/>
```

## API Service

### FeatureSelectionService

Service class for making API calls:

```typescript
import { FeatureSelectionService } from '@/lib/services/featureSelection'

// Run feature selection
const result = await FeatureSelectionService.selectFeatures(
  datasetId,
  {
    target_column: 'target',
    method: 'random_forest',
    top_k: 10,
    correlation_threshold: 0.7
  },
  session.accessToken
)

// Calculate importance only
const importance = await FeatureSelectionService.calculateImportance(
  datasetId,
  {
    target_column: 'target',
    method: 'mutual_info'
  },
  session.accessToken
)

// Detect redundant features
const redundancy = await FeatureSelectionService.detectRedundancy(
  datasetId,
  { correlation_threshold: 0.8 },
  session.accessToken
)

// Compare multiple methods
const comparison = await FeatureSelectionService.compareMethods(
  datasetId,
  {
    target_column: 'target',
    methods: ['correlation', 'mutual_info', 'random_forest'],
    top_k: 10
  },
  session.accessToken
)
```

## Selection Methods

### Available Algorithms

1. **Correlation** (`correlation`)
   - Fast, interpretable
   - Best for: Linear relationships
   - Use when: Quick analysis needed

2. **Mutual Information** (`mutual_info`)
   - Captures non-linear dependencies
   - Best for: Complex relationships
   - Use when: Data has non-linear patterns

3. **Random Forest** (`random_forest`)
   - Tree-based importance
   - Best for: Feature interactions
   - Use when: Planning to use tree models

4. **RFE** (`rfe`)
   - Recursive feature elimination
   - Best for: Finding optimal subset
   - Use when: Accuracy is critical

5. **LASSO** (`lasso`)
   - L1 regularization
   - Best for: Linear models, sparse solutions
   - Use when: Using linear regression

6. **Statistical** (`statistical`)
   - Chi-squared / F-tests
   - Best for: Large datasets, quick filtering
   - Use when: Need statistical validation

## Integration Example

### Adding to an Existing Page

```tsx
// app/datasets/[id]/features/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { FeatureSelection } from '@/components/FeatureSelection'

export default function FeaturesPage({ params }: { params: { id: string } }) {
  const [columns, setColumns] = useState<string[]>([])

  useEffect(() => {
    // Fetch dataset columns
    async function loadColumns() {
      const response = await fetch(`/api/datasets/${params.id}`)
      const data = await response.json()
      setColumns(data.columns)
    }
    loadColumns()
  }, [params.id])

  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-8">Feature Selection</h1>

      <FeatureSelection
        datasetId={params.id}
        columns={columns}
        onComplete={(result) => {
          console.log('Feature selection complete!')
          console.log('Selected:', result.selected_features)
        }}
      />
    </div>
  )
}
```

## Helper Functions

```typescript
import {
  getMethodName,
  getMethodDescription,
  getMethodUseCase,
  formatExecutionTime
} from '@/lib/services/featureSelection'

// Get display name
const name = getMethodName('random_forest') // "Random Forest"

// Get description
const desc = getMethodDescription('mutual_info')
// "Captures non-linear dependencies using mutual information theory"

// Get use case
const useCase = getMethodUseCase('correlation')
// "Best for: Quick analysis, linear relationships, interpretable results"

// Format time
const time = formatExecutionTime(1523.45) // "1.5s"
```

## Styling

All components use Tailwind CSS and shadcn/ui components for consistent styling. They automatically adapt to your app's theme.

## Error Handling

```tsx
import { FeatureSelection } from '@/components/FeatureSelection'

<FeatureSelection
  datasetId={id}
  columns={columns}
  onComplete={(result) => {
    // Success handling
    console.log('Success:', result)
  }}
  // Errors are displayed automatically in the UI
/>
```

## Performance Tips

1. **Large Datasets**: Use `sample_size` parameter to sample data
2. **Quick Results**: Start with `statistical` method, then try others
3. **Caching**: Results are automatically cached for 1 hour
4. **Progressive Loading**: Use `showOnlySelected` to focus on selected features

## Next Steps

After feature selection, you can:
1. Export results (JSON/CSV)
2. Proceed to model training
3. Save selection for later use
4. Compare with other selection methods
