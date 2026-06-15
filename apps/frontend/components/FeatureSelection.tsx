'use client'

import React, { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import {  Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SelectionControls, type SelectionConfig } from './SelectionControls'
import { FeatureImportanceChart } from './FeatureImportanceChart'
import { SelectedFeatureSet } from './SelectedFeatureSet'
import { MethodComparisonView } from './MethodComparisonView'
import {
  FeatureSelectionService,
  type FeatureSelectionResult,
  type MethodComparisonResponse,
  type SelectionMethod
} from '@/lib/services/featureSelection'

export interface FeatureSelectionProps {
  datasetId: string
  columns: string[]
  defaultTargetColumn?: string
  onComplete?: (result: FeatureSelectionResult) => void
}

export function FeatureSelection({
  datasetId,
  columns,
  defaultTargetColumn,
  onComplete
}: FeatureSelectionProps) {
  const { data: session } = useSession()
  const [config, setConfig] = useState<SelectionConfig>({
    method: 'correlation' as SelectionMethod,
    targetColumn: defaultTargetColumn || '',
    correlationThreshold: 0.7
  })

  const [result, setResult] = useState<FeatureSelectionResult | null>(null)
  const [comparisonResult, setComparisonResult] = useState<MethodComparisonResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'configure' | 'results' | 'comparison'>('configure')

  // Load previously selected features on mount
  useEffect(() => {
    const loadPreviousSelection = async () => {
      if (!session?.accessToken) return

      try {
        const previous = await FeatureSelectionService.getSelectedFeatures(
          datasetId,
          session.accessToken
        )

        if (previous.has_selection && previous.selected_features.length > 0) {
          // Show a notification that previous selection exists
          console.log('Previous feature selection found:', previous.selected_features)
        }
      } catch {
        // Silently fail - no previous selection
        console.log('No previous selection found')
      }
    }

    loadPreviousSelection()
  }, [datasetId, session])

  const handleRunSelection = async () => {
    if (!session?.accessToken) {
      setError('Please sign in to run feature selection')
      return
    }

    if (!config.targetColumn) {
      setError('Please select a target column')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const selectionResult = await FeatureSelectionService.selectFeatures(
        datasetId,
        {
          target_column: config.targetColumn,
          method: config.method,
          top_k: config.topK,
          threshold: config.threshold,
          correlation_threshold: config.correlationThreshold,
          problem_type: config.problemType,
          sample_size: config.sampleSize
        },
        session.accessToken
      )

      setResult(selectionResult)
      setActiveTab('results')
      onComplete?.(selectionResult)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Feature selection failed')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCompare = async () => {
    if (!session?.accessToken) {
      setError('Please sign in to compare methods')
      return
    }

    if (!config.targetColumn) {
      setError('Please select a target column')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      // Run comparison with a selection of methods
      const methods: SelectionMethod[] = [
        'correlation',
        'mutual_info',
        'random_forest',
        'statistical'
      ]

      const comparison = await FeatureSelectionService.compareMethods(
        datasetId,
        {
          target_column: config.targetColumn,
          methods,
          top_k: config.topK || 10,
          problem_type: config.problemType
        },
        session.accessToken
      )

      // Preserve the full comparison response and surface it in the Comparison tab.
      setComparisonResult(comparison)
      setActiveTab('comparison')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Method comparison failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'configure' | 'results' | 'comparison')}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="configure">Configure Selection</TabsTrigger>
          <TabsTrigger value="results" disabled={!result}>
            Results {result && `(${result.selected_features.length} features)`}
          </TabsTrigger>
          <TabsTrigger value="comparison" disabled={!comparisonResult}>
            Comparison {comparisonResult && `(${comparisonResult.results.length} methods)`}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="configure" className="space-y-6">
          <SelectionControls
            config={config}
            onChange={setConfig}
            onRunSelection={handleRunSelection}
            onCompare={handleCompare}
            columns={columns}
            isLoading={isLoading}
          />
        </TabsContent>

        <TabsContent value="results" className="space-y-6">
          {result && (
            <>
              {/* Feature Importance Chart */}
              <FeatureImportanceChart
                features={result.feature_scores}
                highlightThreshold={config.threshold || 0.5}
              />

              {/* Selected Features Summary */}
              <SelectedFeatureSet
                result={result}
                onProceedToModeling={() => {
                  // Navigate to model training page
                  window.location.href = `/datasets/${datasetId}/train`
                }}
              />
            </>
          )}
        </TabsContent>

        <TabsContent value="comparison" className="space-y-6">
          {comparisonResult && (
            <MethodComparisonView comparison={comparisonResult} />
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
