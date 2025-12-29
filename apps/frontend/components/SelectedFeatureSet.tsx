'use client'

import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table'
import type { FeatureSelectionResult, FeatureScore } from '@/lib/services/featureSelection'
import { formatExecutionTime } from '@/lib/services/featureSelection'

export interface SelectedFeatureSetProps {
  result: FeatureSelectionResult
  onExportJSON?: () => void
  onExportCSV?: () => void
  onProceedToModeling?: () => void
}

export function SelectedFeatureSet({
  result,
  onExportJSON,
  onExportCSV,
  onProceedToModeling
}: SelectedFeatureSetProps) {
  const selectedFeatures = result.feature_scores.filter((f) => f.selected)

  const downloadJSON = () => {
    const data = {
      dataset_id: result.dataset_id,
      method: result.method,
      selected_features: result.selected_features,
      feature_scores: selectedFeatures,
      metadata: result.metadata,
      created_at: result.created_at
    }

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json'
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `feature-selection-${result.dataset_id}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    onExportJSON?.()
  }

  const downloadCSV = () => {
    // Helper function to escape CSV fields per RFC 4180
    const escapeCsvField = (field: string): string => {
      // If field contains comma, quote, or newline, it must be quoted
      if (field.includes(',') || field.includes('"') || field.includes('\n')) {
        // Escape quotes by doubling them, then wrap in quotes
        return `"${field.replace(/"/g, '""')}"`
      }
      return field
    }

    const headers = ['Feature Name', 'Importance Score', 'Rank', 'Selected']
    const rows = result.feature_scores.map((f) => [
      escapeCsvField(f.feature_name),
      f.score.toFixed(6),
      f.rank.toString(),
      f.selected ? 'Yes' : 'No'
    ])

    const csv = [headers.map(escapeCsvField).join(','), ...rows.map((r) => r.join(','))].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `feature-selection-${result.dataset_id}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    onExportCSV?.()
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Selected Features</CardTitle>
            <CardDescription>
              {selectedFeatures.length} features selected out of{' '}
              {result.metadata.n_features_original} original features
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button onClick={downloadJSON} variant="outline" size="sm">
              Export JSON
            </Button>
            <Button onClick={downloadCSV} variant="outline" size="sm">
              Export CSV
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Summary Statistics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-600">Method</p>
            <p className="text-lg font-semibold capitalize">{result.method.replace('_', ' ')}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-600">Problem Type</p>
            <p className="text-lg font-semibold capitalize">{result.metadata.problem_type}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-600">Samples</p>
            <p className="text-lg font-semibold">{result.metadata.n_samples.toLocaleString()}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-600">Execution Time</p>
            <p className="text-lg font-semibold">
              {formatExecutionTime(result.execution_time_ms)}
            </p>
          </div>
        </div>

        {/* Explanation */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-blue-900 mb-2">Selection Explanation</h4>
          <p className="text-sm text-blue-800">{result.explanation}</p>
        </div>

        {/* Redundant Features Warning */}
        {result.redundant_pairs.length > 0 && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-yellow-900 mb-2">
              ⚠️ Highly Correlated Features Detected
            </h4>
            <p className="text-sm text-yellow-800 mb-3">
              Found {result.redundant_pairs.length} pairs of highly correlated features. Consider
              removing one from each pair to reduce multicollinearity.
            </p>
            <div className="space-y-2">
              {result.redundant_pairs.slice(0, 5).map((pair, idx) => (
                <div key={idx} className="flex items-center justify-between text-sm">
                  <span className="text-yellow-900">
                    <Badge variant="outline" className="mr-2">
                      {pair.feature1}
                    </Badge>
                    ↔
                    <Badge variant="outline" className="mx-2">
                      {pair.feature2}
                    </Badge>
                  </span>
                  <span className="text-yellow-700">r = {pair.correlation.toFixed(3)}</span>
                </div>
              ))}
              {result.redundant_pairs.length > 5 && (
                <p className="text-xs text-yellow-700 mt-2">
                  ...and {result.redundant_pairs.length - 5} more pairs
                </p>
              )}
            </div>
          </div>
        )}

        {/* Selected Features Table */}
        <div>
          <h4 className="text-sm font-semibold text-gray-900 mb-3">
            Selected Features ({selectedFeatures.length})
          </h4>
          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rank</TableHead>
                  <TableHead>Feature Name</TableHead>
                  <TableHead className="text-right">Importance Score</TableHead>
                  <TableHead className="text-right">Normalized Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {selectedFeatures.map((feature) => (
                  <TableRow key={feature.feature_name}>
                    <TableCell className="font-medium">#{feature.rank}</TableCell>
                    <TableCell className="font-mono text-sm">{feature.feature_name}</TableCell>
                    <TableCell className="text-right">
                      <Badge
                        variant={
                          feature.score >= 0.8 ? 'default' : feature.score >= 0.5 ? 'secondary' : 'outline'
                        }
                      >
                        {feature.score.toFixed(4)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-24 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{ width: `${feature.score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-600">{(feature.score * 100).toFixed(1)}%</span>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>

        {/* Action Button */}
        {onProceedToModeling && (
          <Button onClick={onProceedToModeling} className="w-full" size="lg">
            Proceed to Model Training
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
